"""Captures self-reported outcomes from users who acted on a recommendation.

Closes the loop on F8 (no-SMS variant): instead of an outbound poll, the frontend
prompts the returning user with "Did you apply for X?" and posts the answer here.
Persisted in MongoDB ``outcomes`` collection with a 180-day TTL so the data team
can compute per-scheme success rates without retaining records indefinitely.
"""

# NOTE: deliberately no `from __future__ import annotations` — Pydantic's TypeAdapter
# can't always resolve string-form annotations on Body params, breaking /openapi.json.

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Body, Request
from pydantic import BaseModel, Field

from backend.rate_limit import limiter
from backend.services.mongo_service import db

router = APIRouter(tags=["outcome"])
logger = logging.getLogger(__name__)

_TRACE_ID_PATTERN = r"^[A-Za-z0-9_-]{0,64}$"
_SESSION_ID_PATTERN = r"^[A-Za-z0-9_:.\-]{0,128}$"
_SCHEME_PATTERN = r"^[\w\s\-/&.()',]{1,120}$"

# Closed enum so ad-hoc strings can't slip in and pollute aggregates.
_VALID_OUTCOMES = ("applied", "received", "rejected", "not_applied", "n/a")


class OutcomeReport(BaseModel):
    scheme: str = Field(..., min_length=1, max_length=120, pattern=_SCHEME_PATTERN)
    outcome: str = Field(..., pattern=r"^(applied|received|rejected|not_applied|n/a)$")
    trace_id: str | None = Field(default=None, max_length=64, pattern=_TRACE_ID_PATTERN)
    session_user_id: str | None = Field(
        default=None, max_length=128, pattern=_SESSION_ID_PATTERN
    )
    note: str | None = Field(default=None, max_length=300)


@router.post(
    "/api/outcome",
    summary="Record a self-reported scheme outcome",
    description=(
        "Returning users tell us whether they applied / received the benefit / were "
        "rejected for a previously-recommended scheme. Stored with a 180-day TTL."
    ),
)
@limiter.limit("3/minute;30/day")
async def handle_outcome(request: Request, body: OutcomeReport = Body(...)):
    if body.outcome not in _VALID_OUTCOMES:
        # Pydantic should already block this, but defence-in-depth in case someone
        # widens the regex in future without updating the enum.
        return {"ok": False, "error": "invalid_outcome"}

    try:
        await db().outcomes.insert_one({
            "scheme": body.scheme.strip(),
            "outcome": body.outcome,
            "trace_id": body.trace_id,
            "session_user_id": body.session_user_id,
            "note": (body.note or "").strip()[:300] or None,
            "ts": datetime.now(timezone.utc),
        })
        logger.info(
            "outcome_stored",
            extra={
                "scheme_prefix": body.scheme[:32],
                "outcome": body.outcome,
                "trace_id": (body.trace_id or "")[:16],
            },
        )
    except Exception:
        logger.warning("outcome_store_failed", exc_info=True)
    return {"ok": True}
