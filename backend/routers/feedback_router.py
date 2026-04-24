"""Collects 👍/👎 reactions and stores them in MongoDB for quality monitoring."""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Body, Request
from pydantic import BaseModel, Field

from backend.rate_limit import limiter
from backend.services.mongo_service import db

router = APIRouter(tags=["feedback"])
logger = logging.getLogger(__name__)


class FeedbackRequest(BaseModel):
    value: str = Field(..., pattern="^(up|down)$")
    trace_id: str | None = Field(default=None, max_length=64)
    session_user_id: str | None = Field(default=None, max_length=128)
    answer_preview: str | None = Field(default=None, max_length=200)
    query_preview: str | None = Field(default=None, max_length=100)


@router.post(
    "/api/feedback",
    summary="Record user 👍/👎 reaction",
    description="Stores reaction in MongoDB feedback collection for offline quality analysis.",
)
@limiter.limit("20/minute")
async def handle_feedback(request: Request, body: FeedbackRequest = Body(...)):
    try:
        await db().feedback.insert_one({
            "value": body.value,
            "trace_id": body.trace_id,
            "session_user_id": body.session_user_id,
            "query_preview": (body.query_preview or "")[:100],
            "answer_preview": (body.answer_preview or "")[:200],
            "ts": datetime.now(timezone.utc),
        })
        logger.info(
            "feedback_stored",
            extra={
                "value": body.value,
                "trace_id": (body.trace_id or "")[:16],
                "session_prefix": (body.session_user_id or "")[:8],
            },
        )
    except Exception:
        logger.warning("feedback_store_failed", exc_info=True)
    return {"ok": True}
