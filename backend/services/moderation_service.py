"""Intent moderation — runs before retrieval."""

from __future__ import annotations

import json
import logging
import re

from backend.config import (
    API_RETRY_ATTEMPTS,
    API_RETRY_BASE_DELAY_S,
    API_RETRY_MAX_DELAY_S,
    MODERATION_CALL_TIMEOUT_S,
    MODERATION_STRICT,
)
from backend.models.response_models import ModerationResult
from backend.prompts.moderation_prompt import MODERATION_PROMPT, MODERATION_PROMPT_TRANSCRIPT
from backend.services import llm_service
from backend.services.resilience import async_retry, log_pipeline_step, with_timeout

logger = logging.getLogger(__name__)

# High-confidence welfare / civic intent — avoids false blocks on short benign queries.
# English/Latin tokens use word boundaries; Devanagari phrases are matched without \\b
# (\\b is unreliable for Hindi script).
_WELFARE_CIVIC_HINT = re.compile(
    r"(?:"
    r"\b(?:scheme|yojana|yojna|pm[-\s]?|pradhan|mantri|aadhaar|aadhar|loan|subsidy|"
    r"welfare|benefit|eligibility|farmer|kisan|woman|women|mahila|student|scholarship|"
    r"ration|ayushman|ujjwala|mudra|housing|pension|bpl|government|sarkari|"
    r"csc|myscheme|apply|documents?|grant|mgnrega|nrega)\b"
    r"|"
    r"मनरेगा|महात्मा\s*गांधी|महात्मा\s*गाँधी|ग्रामीण\s*रोजगार|ग्रामीण\s*रोज़गार|"
    r"योजना|योजनाएं|योजनाओं|स्कीम|स्कीमों|किसान|महिला|छात्र|"
    r"सरकार|सरकारी|लाभ|पेंशन|राशन|आयुष्मान|उज्ज्वला|मुद्रा|आवास|भत्ता|अनुदान|आवेदन|"
    r"बताइए|बताएं|बताओ|जानकारी|दस्तावेज़|पंजीकरण|लाभार्थी|कल्याण"
    r")",
    re.IGNORECASE,
)
# Do not fast-allow when these appear (still run full classifier).
_HARMFUL_HINT = re.compile(
    r"\b(kill|bomb|terror|hack\s+into|credit\s*card\s+number|password\s+for)\b",
    re.IGNORECASE,
)

_FAIL_CLOSED = ModerationResult(
    allowed=False,
    category="moderation_error",
    redirect_message="Sorry, we couldn't verify your request. Please try again shortly.",
)

_FAIL_OPEN = ModerationResult(
    allowed=True,
    category="welfare_scheme",
    redirect_message=None,
)


def _build_moderation_prompt(classifier_input: str, *, conversation: bool) -> str:
    if conversation:
        return MODERATION_PROMPT_TRANSCRIPT.format(transcript=classifier_input)
    return MODERATION_PROMPT.format(query=classifier_input)


def _strip_json_fences(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


def _parse_json_best_effort(raw: str) -> dict:
    cleaned = _strip_json_fences(raw)
    try:
        parsed = json.loads(cleaned)
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        # Some model responses include a short preface/postfix around JSON.
        match = re.search(r"\{[\s\S]*\}", cleaned)
        if not match:
            raise
        parsed = json.loads(match.group(0))
        return parsed if isinstance(parsed, dict) else {}


def _welfare_heuristic_match(text: str) -> bool:
    """True if query looks like welfare / scheme intent (used on classifier failure)."""
    q = (text or "").strip()
    if not q:
        return False
    if _HARMFUL_HINT.search(q):
        return False
    return bool(_WELFARE_CIVIC_HINT.search(q))


def _fast_path_allow(query: str) -> ModerationResult | None:
    """Skip the LLM for obvious on-topic queries (reduces latency and classifier noise)."""
    q = (query or "").strip()
    if not q or len(q) > 400:
        return None
    if _HARMFUL_HINT.search(q):
        return None
    if _WELFARE_CIVIC_HINT.search(q):
        log_pipeline_step("moderation", "fast_allow", "keyword_prefilter")
        return ModerationResult(allowed=True, category="welfare_scheme", redirect_message=None)
    return None


async def _run_moderation_llm(prompt: str) -> str:
    """Gemini moderation call with timeout + exponential retries."""

    async def _once() -> str:
        return await with_timeout(
            llm_service.run_moderation_raw_prompt(prompt),
            seconds=MODERATION_CALL_TIMEOUT_S,
            step="moderation_llm",
        )

    return await async_retry(
        lambda: _once(),
        attempts=API_RETRY_ATTEMPTS,
        base_delay=API_RETRY_BASE_DELAY_S,
        max_delay=API_RETRY_MAX_DELAY_S,
        step="moderation_llm",
    )


async def _classify_intent(classifier_input: str, *, conversation: bool) -> ModerationResult:
    prompt = _build_moderation_prompt(classifier_input, conversation=conversation)
    raw = ""
    try:
        log_pipeline_step("moderation", "llm_start", "classifier")
        raw = await _run_moderation_llm(prompt)
        log_pipeline_step("moderation", "llm_ok", "classifier")
        data = _parse_json_best_effort(raw)
        allowed = bool(data.get("allowed", True))
        category = str(data.get("category", "welfare_scheme"))
        redirect = data.get("redirect_message")
        redirect_message = str(redirect) if redirect is not None else None
        if redirect_message == "null":
            redirect_message = None
        return ModerationResult(
            allowed=allowed,
            category=category,
            redirect_message=redirect_message,
        )
    except json.JSONDecodeError as exc:
        logger.warning(
            "moderation_parse_error reason=json_decode strict=%s conversation=%s error=%s raw_preview=%r",
            MODERATION_STRICT,
            conversation,
            exc,
            (raw[:500] + "…") if len(raw) > 500 else raw,
        )
        return _strict_aware_fallback(classifier_input, reason="json_parse_error")
    except Exception as exc:
        logger.warning(
            "moderation_call_error strict=%s conversation=%s error=%s",
            MODERATION_STRICT,
            conversation,
            exc,
            exc_info=True,
        )
        return _strict_aware_fallback(classifier_input, reason="moderation_call_error")


def _strict_aware_fallback(classifier_input: str, *, reason: str) -> ModerationResult:
    """
    Fallback policy when the classifier raises:
      - MODERATION_STRICT=true  -> fail closed regardless of heuristic, so an attacker
                                   cannot dodge strict mode by including a welfare
                                   keyword in an injection payload.
      - MODERATION_STRICT=false -> fail open if the input looks like a welfare query,
                                   otherwise still fail open (keeps dev UX permissive).
    """
    if MODERATION_STRICT:
        logger.warning(
            "moderation_fallback action=fail_closed reason=%s strict=%s",
            reason,
            MODERATION_STRICT,
        )
        return _FAIL_CLOSED
    if _welfare_heuristic_match(classifier_input):
        logger.warning(
            "moderation_fallback action=fail_open reason=%s_heuristic_welfare strict=%s",
            reason,
            MODERATION_STRICT,
        )
        return _FAIL_OPEN
    logger.warning(
        "moderation_fallback action=fail_open reason=%s strict=%s",
        reason,
        MODERATION_STRICT,
    )
    return _FAIL_OPEN


async def check(query: str, language: str) -> ModerationResult:  # noqa: ARG001 — language reserved for future heuristics
    fp = _fast_path_allow(query)
    if fp is not None:
        return fp
    return await _classify_intent(query, conversation=False)


async def check_conversation_transcript(transcript: str, language: str) -> ModerationResult:  # noqa: ARG001
    """Single moderation pass over full dialogue (e.g. custom LLM) before generation."""
    text = (transcript or "").strip()
    if not text:
        return ModerationResult(allowed=True, category="welfare_scheme", redirect_message=None)
    return await _classify_intent(text, conversation=True)
