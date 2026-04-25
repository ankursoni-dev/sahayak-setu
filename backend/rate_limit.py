"""Shared SlowAPI limiter configuration.

Storage backend defaults to Redis in production (per README) so rate limits are
shared across worker processes; falls back to in-process memory in development.
The user key extractor takes the *last* hop of X-Forwarded-For after the trusted
proxy count, instead of the first (which is client-controllable and trivial to
spoof per request).
"""

from __future__ import annotations

import logging
import os

from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.requests import Request

from backend.config import IS_PRODUCTION, TRUSTED_PROXY_COUNT

logger = logging.getLogger(__name__)


def _user_key(request: Request) -> str:
    """Stable rate-limit key derived from network identity.

    Behind a trusted reverse proxy chain of length N, the client IP is the Nth from
    the right of X-Forwarded-For. Anything to the left was supplied by the client and
    cannot be trusted. With N=0 we ignore XFF and use the socket peer instead.
    """
    if TRUSTED_PROXY_COUNT > 0:
        xff = request.headers.get("x-forwarded-for", "")
        hops = [h.strip() for h in xff.split(",") if h.strip()]
        if hops:
            idx = max(0, len(hops) - TRUSTED_PROXY_COUNT)
            return hops[idx]
    return get_remote_address(request) or "anonymous"


def _resolve_storage_uri() -> str:
    """Pick a SlowAPI storage backend.

    Precedence:
      1. RATE_LIMIT_STORAGE_URI — explicit override (useful for tests/staging)
      2. REDIS_URL when RATE_LIMIT_USE_REDIS is on (default on in production)
      3. memory:// (single-process, dev/test default)
    """
    explicit = os.getenv("RATE_LIMIT_STORAGE_URI", "").strip()
    if explicit:
        return explicit
    use_redis_default = "true" if IS_PRODUCTION else "false"
    use_redis = os.getenv("RATE_LIMIT_USE_REDIS", use_redis_default).strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )
    redis_url = os.getenv("REDIS_URL", "").strip()
    if use_redis and redis_url:
        return redis_url
    if IS_PRODUCTION and use_redis and not redis_url:
        logger.warning("rate_limit_storage_fallback reason=missing_redis_url storage=memory")
    return "memory://"


_STORAGE_URI = _resolve_storage_uri()

limiter = Limiter(
    key_func=_user_key,
    storage_uri=_STORAGE_URI,
    default_limits=["60/minute", "500/hour"],
)
