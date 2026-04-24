"""Vapi webhook freshness + idempotency (replay mitigation within a short window)."""

from __future__ import annotations

import hashlib
import logging
import time
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException

logger = logging.getLogger(__name__)


def _parse_epoch_seconds(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        v = float(value)
        if v > 1e12:  # milliseconds
            return v / 1000.0
        return v
    s = str(value).strip()
    if not s:
        return None
    if s.isdigit():
        vi = int(s)
        return vi / 1000.0 if vi > 1e12 else float(vi)
    try:
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).timestamp()
    except Exception:
        return None


def _as_stable_id(value: Any) -> str | None:
    if value is None or isinstance(value, bool):
        return None
    s = str(value).strip()
    if not s or len(s) > 220:
        return None
    return s


def extract_webhook_delivery_id(parsed: dict[str, Any]) -> str | None:
    """
    Prefer a provider-stable id (call / message id) for dedupe when present,
    so replays can be keyed even if the JSON body differs slightly.
    """
    top = _as_stable_id(parsed.get("id"))
    if top:
        return top
    msg = parsed.get("message")
    if not isinstance(msg, dict):
        return None
    for flat_key in ("callId", "call_id", "webhookId", "webhook_id"):
        v = _as_stable_id(msg.get(flat_key))
        if v:
            return v
    call = msg.get("call")
    if isinstance(call, dict):
        v = _as_stable_id(call.get("id"))
        if v:
            return v
    return _as_stable_id(msg.get("id"))


def extract_webhook_timestamp_seconds(parsed: dict[str, Any]) -> float | None:
    """Best-effort timestamp from signed JSON (body fields only — not unsigned headers)."""
    candidates: list[float] = []
    for key in ("timestamp", "createdAt", "startedAt", "date"):
        ts = _parse_epoch_seconds(parsed.get(key))
        if ts is not None:
            candidates.append(ts)
    msg = parsed.get("message")
    if isinstance(msg, dict):
        for key in ("timestamp", "createdAt", "startedAt"):
            ts = _parse_epoch_seconds(msg.get(key))
            if ts is not None:
                candidates.append(ts)
    return max(candidates) if candidates else None


def assert_webhook_timestamp_fresh(
    *,
    parsed: dict[str, Any],
    max_skew_seconds: int,
    require_timestamp: bool,
) -> None:
    ts = extract_webhook_timestamp_seconds(parsed)
    if ts is None:
        if require_timestamp:
            raise HTTPException(
                status_code=401,
                detail="Webhook payload must include a recognizable timestamp (e.g. message.createdAt).",
            )
        return
    now = time.time()
    if abs(now - ts) > max_skew_seconds:
        raise HTTPException(status_code=401, detail="Webhook timestamp outside allowed window.")


def _webhook_dedupe_material(parsed: dict[str, Any] | None, raw_body: bytes) -> str:
    """Single material hash combining delivery id + body digest."""
    delivery_id = extract_webhook_delivery_id(parsed or {}) or ""
    body_digest = hashlib.sha256(raw_body).hexdigest()
    return hashlib.sha256(f"{delivery_id}\n{body_digest}".encode("utf-8")).hexdigest()


async def reserve_vapi_webhook_idempotency(
    raw_body: bytes,
    parsed: dict[str, Any] | None = None,
    *,
    ttl_seconds: int = 600,
) -> bool:
    """
    Returns True if this request should be processed, False on near-term replay.

    Uses MongoDB webhook_nonces collection with unique _id — TTL index on `ts`
    expires nonces after the replay window (configured in mongo_service.ensure_indexes).
    """
    from datetime import datetime, timezone
    from pymongo.errors import DuplicateKeyError
    from backend.services.mongo_service import db

    material = _webhook_dedupe_material(parsed, raw_body)
    try:
        await db().webhook_nonces.insert_one({"_id": material, "ts": datetime.now(timezone.utc)})
        return True
    except DuplicateKeyError:
        return False
    except Exception:
        logger.warning("vapi_webhook_dedupe_mongo_failed", exc_info=True)
        return True
