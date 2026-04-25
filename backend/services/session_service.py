"""MongoDB-backed per-user conversation history."""

from __future__ import annotations

import hashlib
import hmac
import logging
import uuid
from datetime import datetime, timezone

from backend.config import HISTORY_WINDOW, SESSION_SECRET as _SESSION_SECRET_STR
from backend.services.mongo_service import db

# HMAC requires bytes; config exposes the value as a stripped string so a single source
# of truth governs both startup enforcement (in production) and signing here.
SESSION_SECRET = _SESSION_SECRET_STR.encode("utf-8") if _SESSION_SECRET_STR else b""

logger = logging.getLogger(__name__)


def signed_user_id(raw_id: str) -> str:
    if not SESSION_SECRET:
        return raw_id
    sig = hmac.new(SESSION_SECRET, raw_id.encode("utf-8"), hashlib.sha256).hexdigest()[:16]
    return f"{raw_id}:{sig}"


def verify_user_id(signed: str) -> str | None:
    if not SESSION_SECRET:
        return signed
    if ":" not in signed:
        return None
    raw, sig = signed.rsplit(":", 1)
    expected = hmac.new(SESSION_SECRET, raw.encode("utf-8"), hashlib.sha256).hexdigest()[:16]
    return raw if hmac.compare_digest(sig, expected) else None


def resolve_user_id(provided: str | None) -> tuple[str, str]:
    token = (provided or "").strip()
    if token:
        verified = verify_user_id(token)
        if verified:
            return verified, token if SESSION_SECRET else verified
    if SESSION_SECRET:
        raw = f"u-{uuid.uuid4().hex[:16]}"
        return raw, signed_user_id(raw)
    # Local/dev fallback if SESSION_SECRET is not configured.
    return (token or "anonymous"), (token or "anonymous")


async def get_history(user_id: str) -> list[dict]:
    try:
        doc = await db().sessions.find_one({"_id": user_id}, {"messages": 1})
        if not doc:
            return []
        msgs = doc.get("messages") or []
        # Keep only role + content for LLM consumption.
        return [
            {"role": m["role"], "content": m["content"]}
            for m in msgs
            if isinstance(m, dict) and "role" in m and "content" in m
        ][-HISTORY_WINDOW * 2:]
    except Exception as e:
        logger.warning("session_history_unavailable", extra={"error": str(e)[:200]}, exc_info=True)
        return []


async def append(user_id: str, query: str, answer: str) -> None:
    now = datetime.now(timezone.utc)
    try:
        await db().sessions.update_one(
            {"_id": user_id},
            {
                "$push": {
                    "messages": {
                        "$each": [
                            {"role": "user", "content": query, "ts": now},
                            {"role": "assistant", "content": answer, "ts": now},
                        ],
                        "$slice": -HISTORY_WINDOW * 2,
                    }
                },
                "$set": {"updated_at": now},
                "$setOnInsert": {"created_at": now},
            },
            upsert=True,
        )
    except Exception:
        logger.warning("session_append_failed", extra={"user_id": user_id[:24]}, exc_info=True)
