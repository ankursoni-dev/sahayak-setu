"""Dependency readiness probes for runtime orchestration and health endpoints."""

from __future__ import annotations

import asyncio
from typing import Any

from backend.config import OPENROUTER_API_KEY, OPENROUTER_MODEL, openrouter_client, qdrant_client
from backend.services import mongo_service


async def _qdrant_ready() -> bool:
    try:
        await asyncio.wait_for(
            asyncio.to_thread(qdrant_client.get_collections),
            timeout=2.5,
        )
        return True
    except Exception:
        return False


async def _mongo_ready() -> bool:
    try:
        return await asyncio.wait_for(mongo_service.ping(), timeout=2.5)
    except Exception:
        return False


def _llm_ready() -> dict[str, Any]:
    configured = bool(OPENROUTER_API_KEY and openrouter_client is not None)
    return {
        "provider": f"openrouter/{OPENROUTER_MODEL}" if configured else "unconfigured",
        "ready": configured,
    }


async def readiness_snapshot() -> dict[str, Any]:
    qdrant_ok, mongo_ok = await asyncio.gather(_qdrant_ready(), _mongo_ready())
    llm = _llm_ready()
    ready = bool(qdrant_ok and mongo_ok and llm["ready"])
    return {
        "ready": ready,
        "dependencies": {
            "qdrant": "up" if qdrant_ok else "down",
            "mongo": "up" if mongo_ok else "down",
            "llm": llm,
        },
    }
