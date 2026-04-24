"""Shared SlowAPI limiter configuration — in-memory storage."""

from __future__ import annotations

from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.requests import Request


def _user_key(request: Request) -> str:
    # Prefer network identity; never trust client user-id first.
    return (
        request.headers.get("x-forwarded-for", "").split(",")[0].strip()
        or get_remote_address(request)
        or request.headers.get("x-user-id")
    )


limiter = Limiter(
    key_func=_user_key,
    storage_uri="memory://",
    default_limits=["60/minute", "500/hour"],
)
