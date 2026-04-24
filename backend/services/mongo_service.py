"""MongoDB client singleton + one-time index setup."""

from __future__ import annotations

import logging
import os

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo import ASCENDING

logger = logging.getLogger(__name__)

MONGODB_URL = (os.getenv("MONGODB_URL") or "").strip()
MONGODB_DB = (os.getenv("MONGODB_DB") or "sahayaksetu").strip()

_client: AsyncIOMotorClient | None = None
_indexes_ready = False


def _get_client() -> AsyncIOMotorClient:
    global _client
    if _client is None:
        if not MONGODB_URL:
            raise RuntimeError("MONGODB_URL not configured")
        _client = AsyncIOMotorClient(
            MONGODB_URL,
            serverSelectionTimeoutMS=3000,
            connectTimeoutMS=3000,
        )
    return _client


def db() -> AsyncIOMotorDatabase:
    return _get_client()[MONGODB_DB]


async def ensure_indexes() -> None:
    """Create TTL indexes for auto-expiry. Idempotent — safe to call on every startup."""
    global _indexes_ready
    if _indexes_ready:
        return
    try:
        # sessions: auto-expire after 24h of inactivity
        await db().sessions.create_index(
            [("updated_at", ASCENDING)],
            expireAfterSeconds=60 * 60 * 24,
        )
        # webhook_nonces: auto-expire 5 min after insert (replay window)
        await db().webhook_nonces.create_index(
            [("ts", ASCENDING)],
            expireAfterSeconds=300,
        )
        _indexes_ready = True
        logger.info("mongo_indexes_ready")
    except Exception as e:
        logger.warning("mongo_indexes_failed", extra={"error": str(e)[:200]})


async def ping() -> bool:
    try:
        await _get_client().admin.command("ping")
        return True
    except Exception:
        return False
