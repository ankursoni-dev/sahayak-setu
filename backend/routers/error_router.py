"""Receives frontend error reports for server-side logging and correlation."""

import logging

from fastapi import APIRouter, Body, Request
from pydantic import BaseModel, Field

from backend.rate_limit import limiter

router = APIRouter(tags=["telemetry"])
logger = logging.getLogger(__name__)


_TRACE_ID_PATTERN = r"^[A-Za-z0-9_-]{0,64}$"
_LANG_PATTERN = r"^[A-Za-z0-9_\-]{0,16}$"
# Strip control characters from previews to keep log output single-line.
_QUERY_PREFIX_PATTERN = r"^[^\r\n\t\x00]{0,50}$"
_ERROR_CODE_PATTERN = r"^[A-Za-z0-9_.\- ]{0,100}$"


class ErrorReport(BaseModel):
    error: str = Field(..., max_length=100, pattern=_ERROR_CODE_PATTERN)
    trace_id: str | None = Field(default=None, max_length=64, pattern=_TRACE_ID_PATTERN)
    http_status: int | None = Field(default=None, ge=0, le=599)
    language: str | None = Field(default=None, max_length=16, pattern=_LANG_PATTERN)
    query_prefix: str | None = Field(default=None, max_length=50, pattern=_QUERY_PREFIX_PATTERN)


@router.post(
    "/api/error",
    summary="Record a client-side error report",
    description="Fire-and-forget from the frontend error boundary / fetch wrappers.",
)
@limiter.limit("5/minute;50/hour")
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
