"""Per-Vapi-call ephemeral context, used for voice follow-up menu (F5).

Voice users can't scroll back to a card to re-read documents or eligibility — once
the assistant has spoken, the information is gone. This service caches a small
structured view of the last answered query (keyed by Vapi ``call_id``) so the
follow-up tool ``get_section`` can return "documents", "eligibility", or "apply"
without re-running retrieval.

Storage: MongoDB ``voice_sessions`` with a 30-minute TTL — long enough for a single
call to wrap up, short enough to never accumulate.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any

from backend.services.mongo_service import db

logger = logging.getLogger(__name__)

VOICE_SESSION_TTL_SECONDS = 30 * 60


_DOC_PATTERNS = [
    re.compile(r"documents?\s+(?:needed|required|necessary)[\s:]*(.+?)(?=(?:apply at|how to apply|eligibility|$))", re.I | re.S),
    re.compile(r"दस्तावेज़\s*(?:चाहिए|ज़रूरी)?[\s:।]*(.+?)(?=(?:आवेदन|पात्रता|$))", re.S),
]
_ELIGIBILITY_PATTERNS = [
    re.compile(r"eligibility[\s:]*(.+?)(?=(?:documents|apply at|how to apply|$))", re.I | re.S),
    re.compile(r"पात्रता[\s:।]*(.+?)(?=(?:दस्तावेज़|आवेदन|$))", re.S),
]
_APPLY_PATTERNS = [
    re.compile(r"(?:apply at|how to apply)[\s:]*(.+?)(?=(?:documents|eligibility|$))", re.I | re.S),
    re.compile(r"आवेदन[\s:।]*(.+?)(?=(?:दस्तावेज़|पात्रता|$))", re.S),
]


def _first_match(patterns: list[re.Pattern[str]], text: str) -> str | None:
    for p in patterns:
        m = p.search(text)
        if m and m.group(1).strip():
            # Trim to a reasonable voice length — anything longer is hard to follow.
            return m.group(1).strip()[:600]
    return None


def derive_section_text(document: str) -> dict[str, str | None]:
    """Best-effort split of a scheme chunk into the three follow-up sections.

    Falls back to ``None`` for any section we can't locate; the voice handler then
    politely tells the user "I don't have that section yet" instead of hallucinating.
    """
    if not document:
        return {"documents": None, "eligibility": None, "apply": None}
    return {
        "documents": _first_match(_DOC_PATTERNS, document),
        "eligibility": _first_match(_ELIGIBILITY_PATTERNS, document),
        "apply": _first_match(_APPLY_PATTERNS, document),
    }


async def set_voice_context(call_id: str, *, scheme: str, document: str, apply_link: str | None) -> None:
    """Cache the latest retrieved context for a Vapi call. Idempotent (overwrites)."""
    if not call_id:
        return
    sections = derive_section_text(document or "")
    try:
        await db().voice_sessions.update_one(
            {"_id": call_id},
            {
                "$set": {
                    "scheme": scheme,
                    "documents": sections["documents"],
                    "eligibility": sections["eligibility"],
                    "apply": sections["apply"] or apply_link,
                    "ts": datetime.now(timezone.utc),
                }
            },
            upsert=True,
        )
    except Exception:
        logger.warning("voice_session_set_failed", extra={"call_id": call_id[:24]}, exc_info=True)


async def get_voice_context(call_id: str) -> dict[str, Any] | None:
    if not call_id:
        return None
    try:
        return await db().voice_sessions.find_one({"_id": call_id})
    except Exception:
        logger.warning("voice_session_get_failed", extra={"call_id": call_id[:24]}, exc_info=True)
        return None


async def get_section(call_id: str, section: str) -> str | None:
    """Return the requested section of the last cached context, or None."""
    ctx = await get_voice_context(call_id)
    if not ctx:
        return None
    key = section.strip().lower()
    if key in ("documents", "document", "docs", "papers", "kaagaz", "दस्तावेज़", "दस्तावेज"):
        return ctx.get("documents")
    if key in ("eligibility", "eligible", "criteria", "पात्रता", "योग्यता"):
        return ctx.get("eligibility")
    if key in ("apply", "how to apply", "application", "आवेदन"):
        return ctx.get("apply")
    return None
