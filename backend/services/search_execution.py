"""Resilient /api/search orchestration — step logging and soft failure boundaries."""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable

from fastapi import HTTPException

from backend.config import (
    DEBUG_RETRIEVAL,
    HYBRID_RETRIEVAL,
    LLM_JSON_MODE,
    RETRIEVAL_HARD_FLOOR,
    RETRIEVAL_SOFT_FLOOR,
    SIMILARITY_THRESHOLD,
)
from backend.models.request_models import SearchRequest
from backend.models.response_models import EligibilityHint, SchemeSource, SearchResponse
from backend.services import (
    agent_service,
    eligibility_service,
    grounding_service,
    injection_guard,
    language_service,
    llm_service,
    moderation_service,
    pii_scrubber,
    retrieval_service,
    session_service,
)
from backend.services.resilience import log_pipeline_step

import json as _json
import re as _re


def _unwrap_json_answer(text: str) -> str | None:
    """If the LLM returned a JSON envelope instead of marker-formatted prose, pull the
    'answer' field out. Returns None when the text isn't a parseable JSON object or
    has no usable answer field.
    """
    if not text:
        return None
    stripped = text.strip()
    if not stripped.startswith("{") or not stripped.endswith("}"):
        return None
    try:
        obj = _json.loads(stripped)
    except Exception:
        return None
    if not isinstance(obj, dict):
        return None
    ans = obj.get("answer")
    if isinstance(ans, str) and ans.strip():
        return ans.strip()
    return None

logger = logging.getLogger(__name__)

_PROFILE_INJECTION_RE = _re.compile(
    r"(ignore|disregard).{0,30}(instruction|rule|prompt)|system\s*prompt|<\|.*\|>|<<<|>>>",
    _re.IGNORECASE,
)


def _sanitize_profile(profile: dict) -> dict:
    """Strip injection strings from user-supplied profile before injecting into LLM prompts."""
    clean: dict = {}
    for k, v in profile.items():
        if isinstance(v, str):
            s = v[:200]  # hard length cap
            s = _PROFILE_INJECTION_RE.sub("", s).strip()
            clean[k] = s
        elif isinstance(v, (int, float, bool)) or v is None:
            clean[k] = v
        # drop unexpected types (lists, dicts) entirely
    return clean


def _user_state_from_profile(profile: dict) -> str | None:
    state = profile.get("state") if isinstance(profile, dict) else None
    if not isinstance(state, str):
        return None
    cleaned = state.strip()
    return cleaned or None


def _state_match(user_state: str | None, availability) -> str | None:
    """Compare a user's home state against a scheme's state_availability metadata.

    Returns:
      - None when the user hasn't supplied a state (no pill rendered)
      - "available"     when the scheme runs nationwide or in the user's state
      - "not_available" when the scheme is state-specific and excludes the user's state
      - "unknown_state" when the scheme has no availability data
    """
    if not user_state:
        return None
    if availability in (None, "", []):
        return "unknown_state"
    if isinstance(availability, str):
        return "available" if availability.strip().lower() == "all" else "unknown_state"
    if isinstance(availability, list):
        states = {str(s).strip().lower() for s in availability if isinstance(s, str)}
        return "available" if user_state.strip().lower() in states else "not_available"
    return "unknown_state"


def _build_scheme_source(result, user_state: str | None) -> SchemeSource:
    return SchemeSource(
        scheme=result.scheme_name,
        score=result.score,
        apply_link=result.apply_link,
        source=result.source,
        confidence_label=retrieval_service.confidence_label_for_score(result.score),
        cta_label=retrieval_service.cta_label_for_score(result.score),
        preview_text=retrieval_service.preview_snippet_from_document(result.document),
        last_verified_at=getattr(result, "last_verified_at", None),
        state_availability=getattr(result, "state_availability", None),
        state_match=_state_match(user_state, getattr(result, "state_availability", None)),
        matched_terms=list(getattr(result, "matched_terms", []) or []),
    )


def _confidence_bucket(top_score: float) -> str:
    if top_score > 0.6:
        return "high"
    if top_score >= 0.4:
        return "medium"
    return "low"


def _query_type(query: str) -> str:
    tokens = (query or "").split()
    if len(tokens) <= 3:
        return "short"
    if any(ch.isdigit() for ch in (query or "")):
        return "numeric"
    return "detailed"


def _guided_fallback(language: str) -> tuple[str, str]:
    lang = (language or "").lower()
    if lang.startswith("hi"):
        return (
            "मुझे इसका सटीक मिलान नहीं मिला। मैं इसे बेहतर ढंग से ढूंढने में मदद कर सकता हूँ।",
            "कृपया अपना राज्य, वार्षिक आय और श्रेणी (किसान/छात्र/महिला आदि) बताएं।",
        )
    return (
        "I couldn't find an exact verified match yet. I can help refine this.",
        "Please share your state, annual income, and category (farmer/student/woman/etc.).",
    )


async def execute_search(
    search_request: SearchRequest,
    stream_emit: Callable[[dict[str, object]], Awaitable[None]] | None = None,
) -> SearchResponse:
    raw_user_id, signed_user_id = session_service.resolve_user_id(search_request.user_id)
    _t0 = time.monotonic()
    _t: dict[str, float] = {}
    try:
        log_pipeline_step("search", "start", "")
        raw_query = search_request.query or ""
        safe_query, suspicious = injection_guard.sanitize_query(raw_query)
        if suspicious:
            log_pipeline_step("injection_guard", "flagged", "soft_block")
            return SearchResponse(
                answer=None,
                provider=None,
                sources=[],
                moderation_blocked=True,
                moderation_category="harmful",
                redirect_message="Please ask only about government schemes and civic services.",
                session_user_id=signed_user_id,
            )

        clean_query, pii_hits = pii_scrubber.scrub(safe_query)
        original_query = clean_query.strip()
        if len(original_query) > 300:
            guided_answer, guided_next_step = _guided_fallback(search_request.language)
            qtype = _query_type(original_query)
            return SearchResponse(
                answer=guided_answer,
                provider="query-too-long",
                sources=[],
                moderation_blocked=False,
                redirect_message=None,
                reasoning_why=None,
                near_miss_text=None,
                near_miss_sources=[],
                session_user_id=signed_user_id,
                confidence="low",
                next_step=guided_next_step,
                query_debug={"original": original_query, "rewritten": original_query, "type": qtype},
            )

        normalized_surface = language_service.normalize_hinglish(original_query)
        detected_lang = language_service.detect_language_code(normalized_surface or original_query)
        lang_register_hint = language_service.register_hint(detected_lang, search_request.language)
        qtype = _query_type(original_query)
        rewritten_base = (normalized_surface or original_query).strip() or original_query
        prefer_original_retrieval = language_service.prefer_original_for_retrieval(
            original_query, normalized_surface
        )

        # Moderation and (speculative) query rewrite run in parallel to cut latency.
        # Rewrite is cancelled+discarded when moderation blocks the query.
        log_pipeline_step("moderation", "start", "")
        mod_task = asyncio.create_task(
            moderation_service.check(clean_query, search_request.language)
        )
        rewrite_task: asyncio.Task | None = None
        if len(rewritten_base.split()) <= 5 and not prefer_original_retrieval:
            rewrite_task = asyncio.create_task(
                llm_service.rewrite_query(rewritten_base, search_request.language)
            )

        moderation = await mod_task
        if not moderation.allowed:
            log_pipeline_step("moderation", "blocked", moderation.category or "")
            if rewrite_task is not None:
                rewrite_task.cancel()
            return SearchResponse(
                answer=None,
                provider=None,
                sources=[],
                moderation_blocked=True,
                moderation_category=moderation.category,
                redirect_message=moderation.redirect_message
                or "Please ask about Indian government schemes or civic services.",
            )
        log_pipeline_step("moderation", "allowed", moderation.category or "ok")
        _t["moderation_ms"] = round((time.monotonic() - _t0) * 1000)

        rewritten_query = rewritten_base
        if rewrite_task is not None:
            try:
                rewritten_query = await rewrite_task
            except (asyncio.CancelledError, Exception):
                rewritten_query = rewritten_base
        # When prefer_original is True (query names a specific scheme in Latin script),
        # use the un-normalized original so catalog keyword search matches English documents.
        # Hinglish-normalized form has Devanagari tokens ("किसान") that won't match
        # Latin "kisan" in the English catalog — vector search handles multilingual fine.
        retrieval_query = original_query if prefer_original_retrieval else rewritten_query
        query_debug = {
            "original": original_query,
            "hinglish_normalized": normalized_surface
            if normalized_surface.strip() != original_query.strip()
            else None,
            "detected_language": detected_lang,
            "rewritten": rewritten_query,
            "retrieval_query": retrieval_query,
            "skipped_llm_query_rewrite": prefer_original_retrieval,
            "type": qtype,
            "pii_redactions": pii_hits,
        }

        relevant_results: list = []
        near_miss_results: list = []
        context = ""
        near_miss_context = ""
        retrieval_debug = None
        try:
            relevant_results, near_miss_results, context, near_miss_context = (
                retrieval_service.retrieve_for_rag(
                    retrieval_query,
                    SIMILARITY_THRESHOLD,
                    use_hybrid=HYBRID_RETRIEVAL,
                    boost_query=original_query,
                )
            )
            _t["retrieval_ms"] = round((time.monotonic() - _t0) * 1000)
            log_pipeline_step(
                "retrieval",
                "ok",
                f"relevant={len(relevant_results)} near_miss={len(near_miss_results)}",
            )
        except Exception as e:
            logger.warning("retrieval_failed_soft", extra={"error": str(e)[:200]}, exc_info=True)
            log_pipeline_step("retrieval", "error", str(e)[:200])
            relevant_results, near_miss_results = [], []
            context, near_miss_context = "", ""

        retrieval_debug = (
            retrieval_service.build_retrieval_debug(retrieval_query, relevant_results)
            if DEBUG_RETRIEVAL
            else None
        )

        citation_index_block = retrieval_service.format_citation_index(relevant_results)
        source_index_block = retrieval_service.format_source_index(relevant_results)

        fallback = grounding_service.fallback_text_for_language(search_request.language)
        guided_answer, guided_next_step = _guided_fallback(search_request.language)
        top_score = max((r.score for r in relevant_results), default=0.0)
        if not relevant_results:
            log_pipeline_step("search", "early_exit", "no_results")
            return SearchResponse(
                answer=guided_answer,
                provider="retrieval-empty",
                sources=[],
                moderation_blocked=False,
                redirect_message=None,
                reasoning_why=None,
                near_miss_text=None,
                near_miss_sources=[],
                session_user_id=signed_user_id,
                confidence="low",
                next_step=guided_next_step,
                retrieval_debug=retrieval_debug,
                query_debug=query_debug,
            )

        # Catalog fallback (no Qdrant) returns keyword scores which are not comparable
        # to vector scores. Detect this by checking that all results have vector_score=0.
        is_catalog_fallback = bool(relevant_results) and all(
            r.vector_score == 0.0 for r in relevant_results
        )
        effective_soft_floor = 0.05 if is_catalog_fallback else RETRIEVAL_SOFT_FLOOR
        effective_hard_floor = 0.10 if is_catalog_fallback else RETRIEVAL_HARD_FLOOR

        score_spread = top_score - min((r.score for r in relevant_results), default=top_score)
        if score_spread < 0.05 and top_score < effective_hard_floor:
            return SearchResponse(
                answer=guided_answer,
                provider="retrieval-ambiguous",
                sources=[],
                moderation_blocked=False,
                redirect_message=None,
                reasoning_why=None,
                near_miss_text=None,
                near_miss_sources=[],
                session_user_id=signed_user_id,
                confidence="low",
                next_step=guided_next_step,
                retrieval_debug=retrieval_debug,
                query_debug=query_debug,
            )

        if top_score < effective_soft_floor:
            return SearchResponse(
                answer=guided_answer,
                provider="retrieval-soft-gate",
                sources=[],
                moderation_blocked=False,
                redirect_message=None,
                reasoning_why=None,
                near_miss_text=None,
                near_miss_sources=[],
                session_user_id=signed_user_id,
                confidence="low",
                next_step=guided_next_step,
                retrieval_debug=retrieval_debug,
                query_debug=query_debug,
            )

        history = await session_service.get_history(raw_user_id)
        use_json_llm = LLM_JSON_MODE and stream_emit is None
        messages = llm_service.build_messages(
            original_query,
            context,
            history,
            search_request.language,
            near_miss_context=near_miss_context,
            citation_index_block=citation_index_block,
            source_index_block=source_index_block,
            json_mode=use_json_llm,
            detected_query_language=detected_lang,
            language_register_hint=lang_register_hint,
        )
        answer_main = fallback
        reasoning_why = near_miss_text = None
        provider = None
        log_pipeline_step("llm", "start", "generate")
        if use_json_llm:
            try:
                structured, provider = await llm_service.generate_json(messages)
                verified = await asyncio.to_thread(
                    grounding_service.verify, structured, relevant_results, fallback
                )
                answer_main = verified.answer or fallback
                cleaned = [x.strip() for x in verified.why_it_fits if x and x.strip()]
                reasoning_why = "\n".join(f"- {x}" for x in cleaned) if cleaned else None
                near_miss_text = (verified.near_miss or "").strip() or None
            except Exception as e:
                logger.warning("llm_json_path_failed_falling_back", extra={"error": str(e)[:200]})
                # Rebuild messages in marker mode — reusing the JSON-mode messages causes
                # the LLM to keep emitting JSON which parse_structured_response cannot unwrap.
                marker_messages = llm_service.build_messages(
                    original_query,
                    context,
                    history,
                    search_request.language,
                    near_miss_context=near_miss_context,
                    citation_index_block=citation_index_block,
                    source_index_block=source_index_block,
                    json_mode=False,
                    detected_query_language=detected_lang,
                    language_register_hint=lang_register_hint,
                )
                raw_text, provider = await llm_service.generate(marker_messages)
                answer_main, reasoning_why, near_miss_text = llm_service.parse_structured_response(
                    raw_text
                )
                # Last-resort safety net: if the model still returned a JSON object instead
                # of marker-formatted prose, unwrap the `answer` field so users don't see
                # raw JSON in the UI.
                answer_main = _unwrap_json_answer(answer_main) or answer_main
        elif stream_emit is not None:

            async def _emit_token(t: str) -> None:
                if t:
                    await stream_emit({"type": "token", "text": t})

            raw_text, provider = await llm_service.generate_stream(messages, _emit_token)
            answer_main, reasoning_why, near_miss_text = llm_service.parse_structured_response(raw_text)
        else:
            raw_text, provider = await llm_service.generate(messages)
            answer_main, reasoning_why, near_miss_text = llm_service.parse_structured_response(raw_text)
        _t["llm_ms"] = round((time.monotonic() - _t0) * 1000)
        log_pipeline_step("llm", "ok", provider or "")

        max_n = len(relevant_results)
        answer_main = llm_service.validate_citations_in_answer(answer_main, max_n)
        answer_main = llm_service.dedupe_citations(answer_main)
        if reasoning_why:
            reasoning_why = llm_service.dedupe_citations(
                llm_service.validate_citations_in_answer(reasoning_why, max_n)
            ).strip() or None
        if near_miss_text:
            near_miss_text = llm_service.dedupe_citations(
                llm_service.validate_citations_in_answer(near_miss_text, max_n)
            ).strip() or None
        session_text = llm_service.compose_session_assistant_text(
            answer_main,
            reasoning_why,
            near_miss_text,
        )
        await session_service.append(raw_user_id, original_query, session_text)

        profile = agent_service.UserProfile(**_sanitize_profile(search_request.profile or {}))
        plan = None
        if search_request.include_plan:
            plan = await agent_service.build_plan(
                original_query,
                profile,
                relevant_results,
                search_request.language,
            )
            _t["plan_ms"] = round((time.monotonic() - _t0) * 1000)

        user_state = _user_state_from_profile(search_request.profile or {})
        sources = [_build_scheme_source(r, user_state) for r in relevant_results]
        near_miss_sources = [_build_scheme_source(r, user_state) for r in near_miss_results]
        raw_hints = eligibility_service.hints_for_schemes(
            search_request.profile or {},
            relevant_results,
            query=original_query,
        )
        eligibility_hints = [EligibilityHint(**h) for h in raw_hints]

        response = SearchResponse(
            answer=answer_main,
            provider=provider,
            sources=sources,
            moderation_blocked=False,
            redirect_message=None,
            reasoning_why=reasoning_why,
            near_miss_text=near_miss_text,
            near_miss_sources=near_miss_sources,
            session_user_id=signed_user_id,
            confidence=_confidence_bucket(top_score),
            next_step=(
                guided_next_step
                if RETRIEVAL_SOFT_FLOOR <= top_score < RETRIEVAL_HARD_FLOOR
                else None
            ),
            retrieval_debug=retrieval_debug,
            query_debug=query_debug,
            plan=plan.model_dump() if plan is not None else None,
            eligibility_hints=eligibility_hints,
        )
        _t["total_ms"] = round((time.monotonic() - _t0) * 1000)
        response.timing_ms = _t

        logger.info(
            "request_complete",
            extra={
                "language": search_request.language,
                "provider": provider,
                "sources_count": len(sources),
                "confidence": _confidence_bucket(top_score),
                "plan_included": search_request.include_plan,
                "moderation_category": moderation.category,
                "timing_ms": _t,
            },
        )
        log_pipeline_step("search", "complete", "ok")
        return response
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("search_execution_error", extra={"error": str(e)[:200]})
        guided_answer, guided_next_step = _guided_fallback(search_request.language)
        log_pipeline_step("search", "error_fallback", str(e)[:120])
        return SearchResponse(
            answer=guided_answer,
            provider="error-fallback",
            sources=[],
            moderation_blocked=False,
            redirect_message=None,
            reasoning_why=None,
            near_miss_text=None,
            near_miss_sources=[],
            session_user_id=signed_user_id,
            confidence="low",
            next_step=guided_next_step,
        )
