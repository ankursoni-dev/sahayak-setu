"""LLM generation — OpenRouter (OpenAI-compatible) for all paths."""

from __future__ import annotations

import asyncio
import json
import logging
import queue
import re
import threading
from collections.abc import Awaitable, Callable

from backend.config import (
    AGENT_PLAN_CALL_TIMEOUT_S,
    LLM_CALL_TIMEOUT_S,
    API_RETRY_ATTEMPTS,
    API_RETRY_BASE_DELAY_S,
    API_RETRY_MAX_DELAY_S,
    MAX_PROMPT_CHARS,
    OPENROUTER_MODEL,
    RACE_MODELS,
    REWRITE_QUERY_TIMEOUT_S,
    openrouter_client,
)
from backend.logging_setup import trace_id_var
from backend.services.llm_cost import log_usage
from backend.services.resilience import async_retry, with_timeout
from backend.prompts.system_prompt import SYSTEM_PROMPT
logger = logging.getLogger(__name__)

MARK_ANSWER = "<<<ANSWER>>>"
MARK_WHY = "<<<WHY_IT_FITS>>>"
MARK_NEAR = "<<<NEAR_MISS>>>"


def _openrouter_provider_label() -> str:
    return f"openrouter/{OPENROUTER_MODEL}"

STRUCTURED_SUFFIX = f"""
---
OUTPUT STRUCTURE (keep these marker lines EXACTLY in English; all other content in Target Language):

{MARK_ANSWER}
[Main answer. When naming a scheme from the Citation index, put its number in brackets right after the name (e.g. PM-Kisan [1]). End with a 👉 Next step line. No invented URLs.]

{MARK_WHY}
- [Bullet: only if explicitly supported by Database Context; else one line: use the exact honesty phrase from system rules]
- [Optional second bullet only if clearly evidenced]

{MARK_NEAR}
[If Near-miss context below is empty or "(none)", write exactly: None]
[Otherwise 1–2 near-miss schemes: missing condition + one practical tip each]
"""


def build_messages(
    query: str,
    context: str,
    history: list[dict],
    language: str,
    *,
    near_miss_context: str = "",
    citation_index_block: str = "",
    source_index_block: str = "",
    json_mode: bool = False,
    detected_query_language: str | None = None,
    language_register_hint: str | None = None,
) -> list[dict]:
    from backend.config import LLM_HISTORY_MESSAGE_LIMIT

    near_block = (
        near_miss_context.strip()
        if near_miss_context.strip()
        else "(none — do not invent near-miss schemes.)"
    )

    cite_section = ""
    if citation_index_block.strip():
        cite_section = (
            "Citation index (reference numbers for the main answer ONLY — use these exact [n] tokens):\n"
            f"{citation_index_block.strip()}\n\n"
        )

    if json_mode:
        source_section = ""
        if source_index_block.strip():
            source_section = f"SOURCES:\n{source_index_block.strip()}\n\n"
        user_body = (
            f"TARGET_LANGUAGE: {language}\n\n"
            f"{source_section}"
            f"Database Context:\n{context}\n\n"
            f"Question: {query}\n\n"
            "Return strict JSON only with this schema:\n"
            "{"
            '"status":"ok|insufficient_context",'
            '"answer":"string",'
            '"claims":[{"text":"string","source_id":"S1","span":"string"}],'
            '"next_step":"string|null",'
            '"why_it_fits":["string"],'
            '"near_miss":"string|null"'
            "}\n"
            "CRITICAL: The `answer` field is the user-facing reply and MUST ALWAYS be a non-empty string in TARGET_LANGUAGE. "
            "`claims` is the supporting evidence (each claim is one fact + source_id) — it is SEPARATE from `answer` and does not replace it. "
            "When status=ok, `answer` must summarize the relevant scheme(s) in 1–3 sentences and `claims` must list ≥1 fact grounded in SOURCES. "
            "When status=insufficient_context, `claims=[]` and `answer` is a short apology in TARGET_LANGUAGE suggesting the official portal or CSC."
        )
    else:
        user_body = (
            f"Database Context:\n{context}\n\n"
            f"{cite_section}"
            f"Near-miss retrieval context:\n{near_block}\n\n"
            f"Question: {query}"
            f"{STRUCTURED_SUFFIX}"
        )

    lang_extra = ""
    if detected_query_language or language_register_hint:
        parts = []
        if detected_query_language:
            parts.append(f"AUTODETECTED_QUERY_LANGUAGE (ISO 639-1): {detected_query_language}.")
        if language_register_hint:
            parts.append(language_register_hint)
        lang_extra = "\n\n" + " ".join(parts)

    messages: list[dict] = [
        {
            "role": "system",
            "content": f"{SYSTEM_PROMPT}\n\nTARGET RESPONSE LANGUAGE: {language}{lang_extra}",
        }
    ]
    if history:
        messages.extend(history[-LLM_HISTORY_MESSAGE_LIMIT:])
    messages.append(
        {
            "role": "user",
            "content": user_body,
        }
    )
    return messages


def parse_structured_response(text: str) -> tuple[str, str | None, str | None]:
    """Split LLM output into main answer, why-it-fits, near-miss blocks."""
    raw = (text or "").strip()
    if MARK_ANSWER not in raw:
        return raw, None, None

    try:
        tail = raw.split(MARK_ANSWER, 1)[1]
        answer_part = why_part = near_part = None

        if MARK_WHY in tail:
            answer_part, rest = tail.split(MARK_WHY, 1)
            if MARK_NEAR in rest:
                why_part, near_part = rest.split(MARK_NEAR, 1)
            else:
                why_part = rest
        elif MARK_NEAR in tail:
            answer_part, near_part = tail.split(MARK_NEAR, 1)
        else:
            answer_part = tail

        def _clean(s: str | None) -> str | None:
            if s is None:
                return None
            s = s.strip()
            return s or None

        answer = _clean(answer_part) or raw.strip()
        why = _clean(why_part)
        near = _clean(near_part)
        if near and near.lower() in ("none", "none.", "none!"):
            near = None
        return answer, why, near
    except Exception:
        return raw, None, None


def validate_citations_in_answer(answer: str, max_n: int) -> str:
    """Strip [n] markers that are out of range vs. retrieved sources (prevents citation drift)."""
    if not answer:
        return answer

    def _repl(m: re.Match[str]) -> str:
        if max_n <= 0:
            return ""
        n = int(m.group(1))
        return m.group(0) if 1 <= n <= max_n else ""

    return re.sub(r"\[(\d+)\]", _repl, answer)


def dedupe_citations(answer: str) -> str:
    """Keep the first occurrence of each [n]; strip repeats so the answer reads curated, not raw."""
    if not answer:
        return answer

    seen: set[str] = set()

    def _repl(m: re.Match[str]) -> str:
        num = m.group(1)
        if num in seen:
            return ""
        seen.add(num)
        return f"[{num}]"

    out = re.sub(r"\[(\d+)\]", _repl, answer)
    return re.sub(r" {2,}", " ", out)


def compose_session_assistant_text(answer: str, why: str | None, near: str | None) -> str:
    """Plain text stored in session memory (no marker tokens)."""
    parts: list[str] = [answer.strip()]
    if why:
        parts.append("Why this fits:\n" + why.strip())
    if near:
        parts.append("Almost eligible:\n" + near.strip())
    return "\n\n".join(parts)


async def run_moderation_raw_prompt(prompt: str) -> str:
    """Async OpenRouter call for moderation JSON (short prompt text)."""
    response = await asyncio.wait_for(
        asyncio.to_thread(
            openrouter_client.chat.completions.create,
            model=OPENROUTER_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
        ),
        timeout=10.0,
    )
    return (response.choices[0].message.content or "").strip()


_DEGRADED_CHAT = (
    "We're having a brief issue with the AI service. Please try again in a moment. "
    "For verified government schemes, you can also browse myscheme.gov.in."
)


def _trim_messages_for_budget(messages: list[dict], max_chars: int = MAX_PROMPT_CHARS) -> list[dict]:
    if max_chars <= 0:
        return messages
    total = sum(len((m.get("content") or "")) for m in messages if isinstance(m, dict))
    if total <= max_chars:
        return messages
    out = list(messages)
    # Keep system + latest user message; trim oldest conversational history first.
    while len(out) > 2 and total > max_chars:
        removed = out.pop(1)
        total -= len((removed.get("content") or ""))
    if total <= max_chars:
        return out
    # Final guard: truncate latest user message tail-preserving instruction context.
    latest = out[-1]
    content = (latest.get("content") or "")
    keep = max(500, max_chars - sum(len((m.get("content") or "")) for m in out[:-1]))
    if len(content) > keep:
        latest["content"] = content[:keep]
    return out


async def _call_model(
    messages: list[dict],
    model: str,
    *,
    task: str = "generation",
    temperature: float = 0.2,
    response_format: dict | None = None,
    timeout_s: float | None = None,
) -> tuple[str, str]:
    """Call one specific OpenRouter model. Raises on any failure."""
    if openrouter_client is None:
        raise RuntimeError("openrouter_unconfigured")
    msgs = _trim_messages_for_budget(messages)
    kwargs: dict = {"model": model, "messages": msgs, "temperature": temperature}
    if response_format:
        kwargs["response_format"] = response_format
    response = await with_timeout(
        asyncio.to_thread(openrouter_client.chat.completions.create, **kwargs),
        seconds=timeout_s or LLM_CALL_TIMEOUT_S,
        step=f"llm_{model}",
    )
    text = (response.choices[0].message.content or "").strip()
    usage = getattr(response, "usage", None)
    if usage is not None:
        log_usage(
            model=model,
            task=task,
            prompt_tokens=int(getattr(usage, "prompt_tokens", 0) or 0),
            completion_tokens=int(getattr(usage, "completion_tokens", 0) or 0),
            trace_id=trace_id_var.get(),
        )
    return text, f"openrouter/{model}"


async def _race_complete(
    messages: list[dict],
    *,
    task: str = "generation",
    temperature: float = 0.2,
    response_format: dict | None = None,
    timeout_s: float | None = None,
) -> tuple[str, str]:
    """Fire all RACE_MODELS simultaneously; return the first successful response.

    Losers are cancelled immediately once a winner is found. If one model errors
    the race continues until another succeeds or all fail.
    """
    models = RACE_MODELS or [OPENROUTER_MODEL]
    if len(models) == 1:
        return await _call_model(
            messages, models[0],
            task=task, temperature=temperature,
            response_format=response_format, timeout_s=timeout_s,
        )

    pending: set[asyncio.Task] = {
        asyncio.create_task(
            _call_model(
                messages, m,
                task=task, temperature=temperature,
                response_format=response_format, timeout_s=timeout_s,
            )
        )
        for m in models
    }

    result: tuple[str, str] | None = None
    last_exc: BaseException | None = None

    while pending and result is None:
        done, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
        for t in done:
            exc = t.exception()
            if exc is None:
                result = t.result()
                break
            last_exc = exc
            logger.warning("race_model_failed", extra={"error": str(exc)[:120]})

    for t in pending:
        t.cancel()

    if result is not None:
        logger.info("race_winner", extra={"provider": result[1], "task": task})
        return result
    raise last_exc or RuntimeError("all_race_models_failed")


async def generate(messages: list[dict]) -> tuple[str, str]:
    """Primary chat completion. Does not raise — returns a safe string if all models fail."""
    try:
        return await async_retry(
            lambda: _race_complete(messages, task="generation", temperature=0.2),
            attempts=API_RETRY_ATTEMPTS,
            base_delay=API_RETRY_BASE_DELAY_S,
            max_delay=API_RETRY_MAX_DELAY_S,
            step="llm_generate_race",
        )
    except Exception as e:
        logger.error("llm_race_failed", extra={"error": str(e)[:200]})
    return _DEGRADED_CHAT, "unavailable"


async def _pump_text_queue(
    q: queue.Queue[str | BaseException | None],
    on_token: Callable[[str], Awaitable[None]],
    *,
    timeout_s: float,
) -> str:
    """Drain a worker thread queue until None; invoke on_token for each text fragment."""
    parts: list[str] = []
    loop = asyncio.get_running_loop()
    deadline = loop.time() + float(timeout_s)
    while True:
        remaining = max(0.01, deadline - loop.time())
        try:
            item = await asyncio.wait_for(asyncio.to_thread(q.get), timeout=remaining)
        except asyncio.TimeoutError:
            raise TimeoutError("llm_stream_timeout") from None
        if item is None:
            break
        if isinstance(item, BaseException):
            raise item
        parts.append(item)
        await on_token(item)
    return "".join(parts)


async def generate_stream(
    messages: list[dict[str, str]],
    on_token: Callable[[str], Awaitable[None]],
) -> tuple[str, str]:
    """Stream chat completion from OpenRouter; tokens via ``on_token``."""

    async def _stream_once() -> tuple[str, str]:
        msgs = _trim_messages_for_budget(messages)
        q: queue.Queue[str | BaseException | None] = queue.Queue()

        def worker() -> None:
            try:
                stream = openrouter_client.chat.completions.create(
                    model=OPENROUTER_MODEL,
                    messages=msgs,
                    temperature=0.2,
                    stream=True,
                )
                for chunk in stream:
                    if not chunk.choices:
                        continue
                    delta = chunk.choices[0].delta
                    piece = getattr(delta, "content", None) if delta else None
                    if piece:
                        q.put(piece)
            except BaseException as exc:
                q.put(exc)
            finally:
                q.put(None)

        threading.Thread(target=worker, daemon=True).start()
        text = (await _pump_text_queue(q, on_token, timeout_s=LLM_CALL_TIMEOUT_S)).strip()
        return text, f"openrouter/{OPENROUTER_MODEL}"

    try:
        return await async_retry(
            lambda: _stream_once(),
            attempts=API_RETRY_ATTEMPTS,
            base_delay=API_RETRY_BASE_DELAY_S,
            max_delay=API_RETRY_MAX_DELAY_S,
            step="llm_stream_openrouter",
        )
    except Exception as e:
        logger.error("llm_stream_failed", extra={"error": str(e)[:200]})
    degraded = _DEGRADED_CHAT
    await on_token(degraded)
    return degraded, "unavailable"


def _insufficient_json_payload() -> dict:
    return {"status": "insufficient_context", "answer": None, "claims": []}


def _flatten_prompt(messages: list[dict]) -> str:
    messages = _trim_messages_for_budget(messages)
    prompt_parts = [f"INSTRUCTIONS:\n{SYSTEM_PROMPT}\n"]
    for msg in messages:
        if msg["role"] != "system":
            role = "User" if msg["role"] == "user" else "Assistant"
            prompt_parts.append(f"{role}: {msg['content']}")
    return "\n".join(prompt_parts)


async def generate_json(messages: list[dict]) -> tuple[dict, str]:
    """Structured response path — race all models in JSON mode."""

    def _parse_dict(raw: str) -> dict:
        data = json.loads((raw or "").strip())
        if not isinstance(data, dict):
            raise ValueError("Structured response is not a JSON object")
        return data

    try:
        text, provider = await _race_complete(
            messages,
            task="generation_json",
            temperature=0.1,
            response_format={"type": "json_object"},
        )
        return _parse_dict(text), provider
    except Exception as e:
        logger.warning("structured_json_degraded", extra={"error": str(e)[:200]})
    return _insufficient_json_payload(), "unavailable"


async def generate_agent_plan_json(prompt: str) -> tuple[dict, str]:
    """Schema-constrained JSON for the action-plan agent. Fails soft: returns {} on total failure."""

    def _parse_dict(raw: str) -> dict:
        data = json.loads((raw or "").strip())
        if not isinstance(data, dict):
            raise ValueError("agent plan response is not a JSON object")
        return data

    messages = [
        {
            "role": "system",
            "content": (
                "You output only a single JSON object matching the welfare action-plan schema. "
                "No markdown, no commentary."
            ),
        },
        {"role": "user", "content": prompt},
    ]
    try:
        text, provider = await _race_complete(
            messages,
            task="agent_plan",
            temperature=0.15,
            response_format={"type": "json_object"},
            timeout_s=AGENT_PLAN_CALL_TIMEOUT_S,
        )
        return _parse_dict(text), provider
    except Exception as e:
        logger.warning("agent_plan_json_failed", extra={"error": str(e)[:200]})
    return {}, f"openrouter/{RACE_MODELS[0] if RACE_MODELS else OPENROUTER_MODEL}"


async def generate_json_prompt(prompt: str) -> tuple[dict, str]:
    """Single-prompt strict JSON generation helper."""
    try:
        response = await asyncio.to_thread(
            openrouter_client.chat.completions.create,
            model=OPENROUTER_MODEL,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.1,
        )
        parsed = json.loads((response.choices[0].message.content or "{}").strip())
        return (parsed if isinstance(parsed, dict) else {}), f"openrouter/{OPENROUTER_MODEL}"
    except Exception:
        return {}, f"openrouter/{OPENROUTER_MODEL}"


async def rewrite_query(query: str, language: str) -> str:
    """Query rewrite for retrieval recall. Fail-open to original query."""
    prompt = (
        "Rewrite this short user query into a precise government-scheme search query for India.\n"
        "Rules:\n"
        "- If the query IS already a specific scheme name (PM Kisan, MGNREGA, Ayushman, Ujjwala, "
        "Mudra, SVANidhi, PMAY, Jan Dhan, Vishwakarma, etc.), return it UNCHANGED.\n"
        "- Otherwise expand: add eligibility context, benefits, documents, or state if present.\n"
        "- Max 20 words. Return ONLY the rewritten query — no quotes, no bullets, no explanation.\n\n"
        f"Target language: {language}\n"
        f"User query: {query}"
    )
    try:
        resp = await with_timeout(
            asyncio.to_thread(
                openrouter_client.chat.completions.create,
                model=OPENROUTER_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
            ),
            seconds=REWRITE_QUERY_TIMEOUT_S,
            step="rewrite_query",
        )
        rewritten = (resp.choices[0].message.content or "").strip()
        if rewritten:
            return rewritten.splitlines()[0].strip()
        return query
    except Exception:
        return query
