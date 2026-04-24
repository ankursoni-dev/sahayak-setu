"""Grounded action-planning agent over retrieved scheme sources."""

from __future__ import annotations

import logging
import re
from typing import Iterable

from pydantic import ValidationError

from backend.models.agent_models import (
    ActionStep,
    AgentPlan,
    EligibilityCheck,
    PlanStatus,
    UserProfile,
)
from backend.services import llm_service
from backend.services.retrieval_service import SearchResult

logger = logging.getLogger(__name__)

# Re-export models for callers that import from this module (e.g. search router).
__all__ = [
    "UserProfile",
    "EligibilityCheck",
    "ActionStep",
    "AgentPlan",
    "build_plan",
    "slots_missing",
]

_MAX_ACTION_LEN = 560
_MAX_WHERE_LEN = 400
_MAX_TIME_LEN = 120
_MAX_DOC_ITEM = 200
_MAX_QUESTION_LEN = 280
_MAX_DISCLAIMER = 900
_MAX_ELIGIBILITY_ROWS = 12
_MAX_STEPS = 8
_MAX_DOCS = 12
_MAX_QUESTIONS = 6


def _truncate(text: str | None, max_len: int) -> str:
    if not text:
        return ""
    s = text.strip()
    return s if len(s) <= max_len else s[: max_len - 1].rstrip() + "…"


def _allowed_urls(sources: list[SearchResult]) -> set[str]:
    out: set[str] = set()
    for s in sources:
        if s.apply_link:
            out.add(s.apply_link.strip())
        if s.source:
            out.add(s.source.strip())
    return out


def _url_grounded(url: str | None, allowed: set[str]) -> bool:
    if not url:
        return True
    u = url.strip()
    return u in allowed


def slots_missing(profile: UserProfile, eligibility: list[EligibilityCheck]) -> list[str]:
    wanted: set[str] = set()
    for entry in eligibility:
        if entry.verdict != "unknown":
            continue
        for criterion in entry.unknown_criteria:
            low = criterion.lower()
            if "income" in low and profile.annual_income is None:
                wanted.add("annual_income")
            if "age" in low and profile.age is None:
                wanted.add("age")
            if "state" in low and profile.state is None:
                wanted.add("state")
            if "land" in low and profile.has_land is None:
                wanted.add("has_land")
            if "bpl" in low and profile.bpl is None:
                wanted.add("bpl")
    return sorted(wanted)


def _disclaimer(language: str) -> str:
    if (language or "").lower().startswith("hi"):
        return "यह सूचना आधिकारिक नहीं है। अंतिम पुष्टि के लिए official portal या CSC जाएं।"
    return "This is unofficial guidance. Confirm final eligibility at the official portal or your nearest CSC."


def _insufficient(language: str) -> AgentPlan:
    return AgentPlan(status="insufficient_data", disclaimer=_disclaimer(language))


def _normalize_source_id(raw: str, valid_ids: set[str]) -> str | None:
    if not raw:
        return None
    s = raw.strip()
    if s in valid_ids:
        return s
    m = re.match(r"^S\s*(\d+)\s*$", s, flags=re.IGNORECASE)
    if m:
        candidate = f"S{int(m.group(1))}"
        return candidate if candidate in valid_ids else None
    return None


def _dedupe_eligibility(rows: Iterable[EligibilityCheck]) -> list[EligibilityCheck]:
    seen: set[tuple[str, str]] = set()
    out: list[EligibilityCheck] = []
    for row in rows:
        key = (row.source_id.strip(), row.scheme.strip())
        if key in seen:
            continue
        seen.add(key)
        out.append(row)
    return out[:_MAX_ELIGIBILITY_ROWS]


def _dedupe_strings(items: Iterable[str], cap: int) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for raw in items:
        s = (raw or "").strip()
        if not s or s in seen:
            continue
        seen.add(s)
        out.append(s)
        if len(out) >= cap:
            break
    return out


def _sanitize_steps(
    steps: Iterable[ActionStep],
    allowed: set[str],
) -> list[ActionStep]:
    cleaned: list[ActionStep] = []
    for step in steps:
        action = _truncate(step.action, _MAX_ACTION_LEN)
        if not action:
            continue
        where_raw = step.where
        if where_raw and not _url_grounded(where_raw, allowed):
            where_raw = None
        where = _truncate(where_raw, _MAX_WHERE_LEN) if where_raw else None
        est = _truncate(step.estimated_time, _MAX_TIME_LEN) if step.estimated_time else None
        cleaned.append(
            ActionStep(
                order=step.order,
                action=action,
                where=where or None,
                estimated_time=est or None,
            )
        )
    # Dedupe by (action, where)
    seen: set[tuple[str, str | None]] = set()
    unique: list[ActionStep] = []
    for s in cleaned:
        key = (s.action, s.where)
        if key in seen:
            continue
        seen.add(key)
        unique.append(s)
    unique.sort(key=lambda x: x.order)
    for i, s in enumerate(unique[:_MAX_STEPS], start=1):
        s.order = i
    return unique[:_MAX_STEPS]


_VALID_VERDICTS = {"eligible", "likely_eligible", "likely_ineligible", "unknown"}

def _coerce_raw_plan(raw: dict) -> dict:
    """Normalise LLM output before Pydantic sees it — coerce unknown verdict values."""
    for row in raw.get("eligibility") or []:
        if isinstance(row, dict) and row.get("verdict") not in _VALID_VERDICTS:
            row["verdict"] = "unknown"
    return raw


def _reconcile_status(plan: AgentPlan, profile: UserProfile) -> None:
    missing = slots_missing(profile, plan.eligibility)
    if missing and plan.status == "plan_ready":
        plan.status = "need_more_info"


def _coerce_status(raw: object) -> PlanStatus:
    if isinstance(raw, str) and raw in ("plan_ready", "need_more_info", "insufficient_data"):
        return raw  # type: ignore[return-value]
    return "insufficient_data"


async def build_plan(
    query: str,
    profile: UserProfile,
    sources: list[SearchResult],
    language: str,
) -> AgentPlan:
    lang = language or "en-IN"
    if not sources:
        return _insufficient(lang)

    valid_ids = {f"S{i+1}" for i in range(len(sources))}
    allowed = _allowed_urls(sources)
    prompt = _build_agent_prompt(query, profile, sources, lang)

    raw: dict = {}
    provider = ""
    try:
        raw, provider = await llm_service.generate_agent_plan_json(prompt)
        if not raw:
            logger.info("agent_plan_empty_llm_response", extra={"provider": provider})
            return _insufficient(lang)
    except Exception as e:
        logger.warning("agent_plan_llm_unexpected_error", extra={"error": str(e)[:200]})
        return _insufficient(lang)

    try:
        plan = AgentPlan.model_validate(_coerce_raw_plan(raw))
    except ValidationError as e:
        logger.info("agent_plan_validation_failed", extra={"errors": str(e)[:300]})
        return _insufficient(lang)

    plan = plan.model_copy(update={"status": _coerce_status(plan.status)})

    plan.eligibility = _dedupe_eligibility(
        [
            EligibilityCheck(
                scheme=sch,
                source_id=nid,
                verdict=e.verdict,
                matched_criteria=[_truncate(x, 200) for x in e.matched_criteria if x],
                missing_criteria=[_truncate(x, 200) for x in e.missing_criteria if x],
                unknown_criteria=[_truncate(x, 200) for x in e.unknown_criteria if x],
            )
            for e in plan.eligibility
            if (nid := _normalize_source_id(e.source_id, valid_ids))
            if (sch := _truncate(e.scheme, 200))
        ]
    )

    plan.documents_needed = [_truncate(d, _MAX_DOC_ITEM) for d in _dedupe_strings(plan.documents_needed, _MAX_DOCS)]

    plan.steps = _sanitize_steps(plan.steps, allowed)

    plan.clarifying_questions = [
        _truncate(q, _MAX_QUESTION_LEN) for q in _dedupe_strings(plan.clarifying_questions, _MAX_QUESTIONS)
    ]

    plan.disclaimer = _truncate(plan.disclaimer, _MAX_DISCLAIMER) or _disclaimer(lang)

    _reconcile_status(plan, profile)

    if plan.status == "insufficient_data":
        plan.eligibility = []
        plan.documents_needed = []
        plan.steps = []
        plan.clarifying_questions = []

    if plan.status == "plan_ready":
        if not plan.steps and not plan.documents_needed and not plan.eligibility:
            return _insufficient(lang)

    return plan


def _build_agent_prompt(query: str, profile: UserProfile, sources: list[SearchResult], language: str) -> str:
    sources_block = "\n".join(
        f"[S{i+1}] {s.scheme_name} — {s.document}"
        + (f"\n    apply: {s.apply_link}" if s.apply_link else "")
        + (f"\n    catalogue: {s.source}" if s.source else "")
        for i, s in enumerate(sources)
    )
    profile_block = profile.model_dump_json(exclude_none=True)
    return AGENT_PROMPT_TEMPLATE.format(
        query=query,
        profile=profile_block,
        sources=sources_block,
        language=language,
        max_steps=_MAX_STEPS,
        max_label=len(sources),
    )


AGENT_PROMPT_TEMPLATE = """You are an action-planning agent for Indian welfare schemes.

USER QUERY: {query}
USER PROFILE (JSON, may be partial): {profile}
TARGET LANGUAGE: {language}

SOURCES (only truth you may use; cite source_id as S1…S{max_label} exactly as below):
{sources}

Produce a JSON object with:
- status: plan_ready | need_more_info | insufficient_data
- eligibility: list of rows with scheme, source_id (e.g. S1), verdict, matched_criteria, missing_criteria, unknown_criteria
- documents_needed: list of strings
- steps: list of objects with fields order, action, where, estimated_time — at most {max_steps} steps
- clarifying_questions: short questions if profile gaps block a verdict
- disclaimer: one sentence that this is unofficial; user must verify on official portals

Rules:
- Every eligibility row MUST use a valid source_id from SOURCES (S1 through S{max_label}).
- Never invent amounts, dates, thresholds, or URLs not present in SOURCES.
- If steps include a URL in where, copy it exactly from that source's apply or catalogue line.
- Translate user-facing strings to TARGET LANGUAGE. Keep JSON keys and scheme names in English.

Verdict selection (follow exactly):
- "eligible": ALL hard eligibility criteria are explicitly confirmed by the profile.
- "likely_eligible": most criteria met; only 1-2 minor or optional criteria unknown.
- "likely_ineligible": at least one hard disqualifying criterion is clearly not met (e.g. income above limit, wrong gender, wrong state).
- "unknown": a critical criterion (income, BPL card, land ownership, state, age) is absent from the profile — cannot determine without asking. Default to "unknown" when in doubt; never guess.

Status:
- plan_ready: profile has enough data for at least one eligible/likely_eligible verdict with action steps.
- need_more_info: key criteria missing — list them in clarifying_questions.
- insufficient_data: SOURCES too thin to generate any plan.
Return ONLY JSON.
"""
