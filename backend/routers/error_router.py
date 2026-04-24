"""Receives frontend error reports for server-side logging and correlation."""

import logging

from fastapi import APIRouter, Body, Request
from pydantic import BaseModel, Field

from backend.rate_limit import limiter

router = APIRouter(tags=["telemetry"])
logger = logging.getLogger(__name__)


class ErrorReport(BaseModel):
    error: str = Field(..., max_length=100)
    trace_id: str | None = Field(default=None, max_length=64)
    http_status: int | None = Field(default=None, ge=0, le=599)
    language: str | None = Field(default=None, max_length=16)
    query_prefix: str | None = Field(default=None, max_length=50)


@router.post(
    "/api/error",
    summary="Record a client-side error report",
    description="Fire-and-forget from the frontend error boundary / fetch wrappers.",
)
@limiter.limit("10/minute")
async def handle_error_report(request: Request, body: ErrorReport = Body(...)):
    logger.warning(
        "frontend_error",
        extra={
            "error_code": body.error,
            "trace_id": (body.trace_id or "")[:16],
            "http_status": body.http_status,
            "language": body.language,
            "query_prefix": (body.query_prefix or "")[:50],
        },
    )
    return {"ok": True}
