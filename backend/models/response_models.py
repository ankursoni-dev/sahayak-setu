from pydantic import BaseModel, Field


class EligibilityHint(BaseModel):
    scheme: str
    verdict: str  # likely_eligible | likely_ineligible | unknown
    reason: str


class SchemeSource(BaseModel):
    scheme: str
    score: float
    apply_link: str | None = None
    source: str | None = None
    confidence_label: str
    cta_label: str
    preview_text: str = ""
    # ISO date (YYYY-MM-DD) the scheme was last verified against the official source.
    # Frontend renders this as a "Verified: <date>" pill so users can judge freshness.
    last_verified_at: str | None = None
    # "all" for nationwide schemes, list[str] of state names for state-specific.
    state_availability: str | list[str] | None = None
    # Computed against the user's profile.state when present:
    # "available" | "unknown_state" | "not_available" | None (when no state given).
    state_match: str | None = None
    # Up to 4 query tokens that overlapped the chunk — drives the "Why this match"
    # explainer. Plain words only; no scores leak.
    matched_terms: list[str] = Field(default_factory=list)


class SearchResponse(BaseModel):
    answer: str | None
    provider: str | None
    sources: list[SchemeSource]
    moderation_blocked: bool = False
    redirect_message: str | None = None
    moderation_category: str | None = None
    reasoning_why: str | None = None
    near_miss_text: str | None = None
    near_miss_sources: list[SchemeSource] = Field(default_factory=list)
    session_user_id: str | None = None
    confidence: str | None = None
    next_step: str | None = None
    retrieval_debug: dict | None = None
    query_debug: dict | None = None
    plan: dict | None = None
    eligibility_hints: list[EligibilityHint] = Field(default_factory=list)
    timing_ms: dict | None = None



class ModerationResult(BaseModel):
    allowed: bool
    category: str
    redirect_message: str | None = None
