"""Shared test fixtures. Stubs Redis so tests run without a live Upstash connection."""

from __future__ import annotations

import os
import pathlib
import sys
from typing import Any

import pytest

# Make `backend.*` importable from the repo root.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

# Sensible defaults for test environment — real credentials from .env are ignored.
os.environ.setdefault("QDRANT_URL", "http://localhost:6333")
os.environ.setdefault("GEMINI_API_KEY", "test-key")
os.environ.setdefault("ENV", "development")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379")


class _FakePipeline:
    def __init__(self, store: dict[str, Any]) -> None:
        self.store = store

    def zadd(self, *_args: Any, **_kwargs: Any) -> "_FakePipeline":
        return self

    def zremrangebyrank(self, *_args: Any, **_kwargs: Any) -> "_FakePipeline":
        return self

    async def execute(self) -> list[int]:
        return [1]


class _FakeRedis:
    def __init__(self) -> None:
        self._store: dict[str, Any] = {}

    def pipeline(self) -> _FakePipeline:
        return _FakePipeline(self._store)

    async def get(self, _key: str) -> None:
        return None

    async def set(self, *_args: Any, **_kwargs: Any) -> bool:
        return True

    async def setex(self, *_args: Any, **_kwargs: Any) -> bool:
        return True

    async def ping(self) -> bool:
        return True


@pytest.fixture(autouse=True)
def _stub_redis(monkeypatch: pytest.MonkeyPatch) -> None:
    """Replace the module-level Redis client so no test touches the network."""
    from backend.services import cache_service, session_service

    fake = _FakeRedis()
    monkeypatch.setattr(session_service, "_client", lambda: fake)
    # cache_service uses session_service._client internally; this chain covers both.
    if hasattr(cache_service, "_client"):
        monkeypatch.setattr(cache_service, "_client", lambda: fake, raising=False)
