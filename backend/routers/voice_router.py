import hmac
import json
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from slowapi.util import get_remote_address

from backend.config import (
    ENV,
    SIMILARITY_THRESHOLD,
    VAPI_WEBHOOK_MAX_SKEW_S,
    VAPI_WEBHOOK_REQUIRE_TIMESTAMP,
    VAPI_WEBHOOK_SECRET,
)
from backend.rate_limit import limiter
from backend.services import injection_guard, moderation_service, pii_scrubber, retrieval_service
from backend.services import vapi_webhook_guard
from backend.services.language_hint import infer_bcp47

router = APIRouter(tags=["voice"])

_ASSISTANT_RESPONSE = {
    "assistant": {
        "model": {
            "provider": "openai",
            "model": "gpt-4o-mini",
        },
        "voice": {"provider": "azure", "voiceId": "hi-IN-SwaraNeural"},
        "firstMessage": (
            "Namaste! Main SahayakSetu hoon. Aap kisi bhi sarkari yojna ke baare mein pooch sakte hain."
        ),
    }
}


def _verify_vapi_signature(request: Request, raw_body: bytes) -> None:
    if not VAPI_WEBHOOK_SECRET:
        if ENV == "production":
            raise HTTPException(
                status_code=503,
                detail={
                    "error": "webhook_secret_not_configured",
                    "message": "Set VAPI_WEBHOOK_SECRET in the server environment to accept Vapi webhooks.",
                },
            )
        return
    sig = (request.headers.get("x-vapi-signature") or "").strip()
    expected = hmac.new(VAPI_WEBHOOK_SECRET.encode("utf-8"), raw_body, "sha256").hexdigest()
    if len(sig) != len(expected) or not hmac.compare_digest(sig, expected):
        raise HTTPException(status_code=401, detail="Invalid signature")


@router.post("/vapi-webhook")
@limiter.limit(
    "30/minute",
    key_func=lambda request: request.headers.get("x-vapi-signature")
    or request.headers.get("x-forwarded-for", "").split(",")[0].strip()
    or get_remote_address(request),
)
async def handle_vapi_webhook(request: Request):
    raw_body = await request.body()
    _verify_vapi_signature(request, raw_body)
    try:
        parsed = json.loads(raw_body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON body") from None
    if not isinstance(parsed, dict):
        raise HTTPException(status_code=400, detail="Webhook body must be a JSON object")
    webhook_body: dict[str, Any] = parsed
    message = webhook_body.get("message", {})

    if VAPI_WEBHOOK_SECRET:
        vapi_webhook_guard.assert_webhook_timestamp_fresh(
            parsed=webhook_body,
            max_skew_seconds=VAPI_WEBHOOK_MAX_SKEW_S,
            require_timestamp=VAPI_WEBHOOK_REQUIRE_TIMESTAMP,
        )
        is_first = await vapi_webhook_guard.reserve_vapi_webhook_idempotency(raw_body, webhook_body)
        if not is_first:
            if message.get("type") == "assistant-request":
                return JSONResponse(content=_ASSISTANT_RESPONSE)
            if message.get("type") == "tool-calls":
                return JSONResponse(content={"results": []})
            return JSONResponse(content={})

    if message.get("type") == "assistant-request":
        return JSONResponse(content=_ASSISTANT_RESPONSE)

    if message.get("type") == "tool-calls":
        tool_calls = message.get("toolCalls", [])
        if not isinstance(tool_calls, list):
            tool_calls = []
        results = []
        for call in tool_calls:
            if not isinstance(call, dict):
                continue
            call_id = call.get("id") or "unknown"
            fn = call.get("function")
            if not isinstance(fn, dict):
                continue
            if fn.get("name") != "search_schemes":
                continue
            raw_args = fn.get("arguments", "{}")
            if isinstance(raw_args, dict):
                args = raw_args
            else:
                try:
                    args = json.loads(str(raw_args) if raw_args is not None else "{}")
                except json.JSONDecodeError:
                    results.append(
                        {
                            "toolCallId": call_id,
                            "result": "Invalid tool arguments; please retry with a clear scheme question.",
                        }
                    )
                    continue
            if not isinstance(args, dict):
                args = {}
            query_text = args.get("query", "")
            query_text, suspicious = injection_guard.sanitize_query(query_text)
            query_text, _ = pii_scrubber.scrub(query_text)
            lang = args.get("language") or infer_bcp47(query_text)

            if suspicious:
                results.append(
                    {
                        "toolCallId": call_id,
                        "result": "Please ask a normal welfare-scheme question and avoid instruction-style prompts.",
                    }
                )
                continue

            moderation = await moderation_service.check(query_text, lang)
            if not moderation.allowed:
                block_text = (
                    moderation.redirect_message
                    or "Please ask about Indian government schemes or civic services."
                )
                results.append({"toolCallId": call_id, "result": block_text})
                continue

            relevant_results, _near_miss_results, context, near_ctx = (
                retrieval_service.retrieve_for_rag(query_text, SIMILARITY_THRESHOLD)
            )
            context_parts = [context] if context.strip() else []
            if near_ctx.strip():
                context_parts.append(near_ctx)
            context = "\n\n".join(context_parts) if context_parts else ""
            results.append(
                {
                    "toolCallId": call_id,
                    "result": context or "Mujhe details nahi mili.",
                }
            )
        return JSONResponse(content={"results": results})

    return JSONResponse(content={})
