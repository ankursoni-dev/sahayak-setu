"""API contract tests: all HTTP entry points, validation, and failure modes."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import pathlib
import sys
import uuid

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
os.environ.setdefault("QDRANT_URL", "http://localhost:6333")
os.environ.setdefault("GEMINI_API_KEY", "test-key")
os.environ.setdefault("ENV", "development")

from backend.main import app  # noqa: E402
from backend.services.retrieval_service import SearchResult  # noqa: E402

client = TestClient(app)


@pytest.fixture(autouse=True)
def _mock_retrieval_and_llm(monkeypatch):
    from backend.services import llm_service, retrieval_service

    async def _rewrite(q: str, _lang: str) -> str:
        return q

    def _retrieve(_q: str, _threshold: float, **_kwargs):
        return (
            [SearchResult(scheme_name="PMAY", document="PMAY info", score=0.8)],
            [],
            "PMAY context",
            "",
        )

    async def _generate_json(_messages):
        return (
            {
                "status": "insufficient_context",
                "answer": None,
                "claims": [],
                "why_it_fits": [],
                "near_miss": None,
                "next_step": None,
            },
            "test-model",
        )

    async def _generate_stream(_messages, on_token):
        await on_token("tok")
        body = (
            f"{llm_service.MARK_ANSWER}\nStreamed answer [1].\n"
            f"{llm_service.MARK_WHY}\n- because\n"
            f"{llm_service.MARK_NEAR}\nNone"
        )
        return body, "test-stream"

    monkeypatch.setattr(llm_service, "rewrite_query", _rewrite)
    monkeypatch.setattr(llm_service, "generate_json", _generate_json)
    monkeypatch.setattr(llm_service, "generate_stream", _generate_stream)
    monkeypatch.setattr(retrieval_service, "retrieve_for_rag", _retrieve)


def test_get_health_returns_online():
    r = client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert data.get("status") == "online"
    assert "model" in data
    assert "threshold" in data


def test_get_root_returns_status():
    r = client.get("/")
    assert r.status_code == 200
    assert "status" in r.json()


def test_get_ready_503_when_not_ready(monkeypatch):
    from backend.routers import health_router

    async def _down():
        return {
            "ready": False,
            "dependencies": {
                "qdrant": "down",
                "redis": "down",
                "llm": {"primary": "x", "fallback": "none", "ready": False},
            },
        }

    monkeypatch.setattr(health_router, "readiness_snapshot", _down)
    r = client.get("/ready")
    assert r.status_code == 503
    body = r.json()
    assert body.get("detail", {}).get("ready") is False


def test_post_search_missing_query_422():
    r = client.post("/api/search", json={"language": "en-IN"})
    assert r.status_code == 422


def test_post_search_query_wrong_type_422():
    r = client.post("/api/search", json={"query": 123, "language": "en-IN"})
    assert r.status_code == 422


def test_post_search_blank_query_422():
    r = client.post("/api/search", json={"query": "   ", "language": "en-IN"})
    assert r.status_code == 422


def test_post_search_oversized_query_422():
    from backend import config

    limit = config.MAX_QUERY_CHARS
    r = client.post("/api/search", json={"query": "x" * (limit + 1), "language": "en-IN"})
    assert r.status_code == 422


def test_search_stream_cache_hit_emits_phase_and_token(monkeypatch):
    from backend.services import cache_service

    async def _fake_get(_q: str, _lang: str):
        return {
            "answer": "cached answer text",
            "provider": "redis-hit",
            "sources": [],
            "moderation_blocked": False,
        }

    monkeypatch.setattr(cache_service, "get", _fake_get)
    with client.stream(
        "POST",
        "/api/search/stream",
        json={"query": "stream cache smoke query", "language": "en-IN"},
    ) as r:
        assert r.status_code == 200
        raw = b"".join(r.iter_bytes())
    lines = [ln for ln in raw.decode("utf-8").strip().split("\n") if ln.strip()]
    types_in_order = [json.loads(ln).get("type") for ln in lines]
    assert types_in_order == ["meta", "phase", "token", "complete"]
    phase = json.loads(lines[1])
    assert phase == {"type": "phase", "name": "cache_hit"}
    tok = json.loads(lines[2])
    assert tok.get("type") == "token" and tok.get("text") == "cached answer text"
    complete = json.loads(lines[-1])
    assert complete.get("type") == "complete"
    assert complete["data"].get("answer") == "cached answer text"


def test_search_stream_returns_ndjson_meta_and_complete():
    # Fresh query each run avoids cache hits so we exercise LLM token streaming.
    with client.stream(
        "POST",
        "/api/search/stream",
        json={"query": f"PMAY stream ndjson {uuid.uuid4().hex}", "language": "en-IN"},
    ) as r:
        assert r.status_code == 200
        raw = b"".join(r.iter_bytes())
    lines = [ln for ln in raw.decode("utf-8").strip().split("\n") if ln.strip()]
    assert len(lines) >= 3
    types_in_order = [json.loads(ln).get("type") for ln in lines]
    assert types_in_order[0] == "meta"
    assert "token" in types_in_order
    assert types_in_order[-1] == "complete"
    meta = json.loads(lines[0])
    assert meta.get("trace_id")
    token_ev = next(x for x in (json.loads(ln) for ln in lines) if x.get("type") == "token")
    assert token_ev.get("text") == "tok"
    complete = json.loads(lines[-1])
    assert complete.get("type") == "complete"
    assert "data" in complete
    assert "moderation_blocked" in complete["data"]


def test_cache_query_normalization_nfkc():
    from backend.services.cache_service import _normalize_cache_query

    a = _normalize_cache_query("  PM\u00a0Kisan  ")
    b = _normalize_cache_query("pm kisan")
    assert a == b


def test_post_search_happy_path_200():
    r = client.post("/api/search", json={"query": "PMAY eligibility Karnataka", "language": "en-IN"})
    assert r.status_code == 200
    data = r.json()
    assert "moderation_blocked" in data


def test_post_search_accepts_optional_profile():
    r = client.post(
        "/api/search",
        json={
            "query": "PM Kisan",
            "language": "hi-IN",
            "profile": {"state": "Karnataka", "annual_income": 120000},
        },
    )
    assert r.status_code == 200


def test_vapi_webhook_invalid_json_returns_400(monkeypatch):
    from backend.routers import voice_router

    monkeypatch.setattr(voice_router, "VAPI_WEBHOOK_SECRET", "")
    monkeypatch.setattr(voice_router, "ENV", "development")
    r = client.post("/vapi-webhook", content=b"not json {{{", headers={"Content-Type": "application/json"})
    assert r.status_code == 400


def test_vapi_webhook_malformed_tool_calls_no_500(monkeypatch):
    from backend.routers import voice_router

    monkeypatch.setattr(voice_router, "VAPI_WEBHOOK_SECRET", "")
    monkeypatch.setattr(voice_router, "ENV", "development")
    body = {
        "message": {
            "type": "tool-calls",
            "toolCalls": [
                "not-a-dict",
                {"id": "1"},
                {"id": "2", "function": "not-dict"},
                {
                    "id": "3",
                    "function": {"name": "search_schemes", "arguments": "not-json"},
                },
                {
                    "id": "4",
                    "function": {
                        "name": "search_schemes",
                        "arguments": json.dumps({"query": "PM Kisan benefits", "language": "en-IN"}),
                    },
                },
            ],
        }
    }
    r = client.post("/vapi-webhook", json=body)
    assert r.status_code == 200
    payload = r.json()
    assert "results" in payload
    ids = {x.get("toolCallId") for x in payload["results"]}
    assert "3" in ids
    assert "4" in ids


def test_vapi_webhook_production_missing_secret_returns_503(monkeypatch):
    from backend.routers import voice_router

    monkeypatch.setattr(voice_router, "VAPI_WEBHOOK_SECRET", "")
    monkeypatch.setattr(voice_router, "ENV", "production")
    r = client.post("/vapi-webhook", json={"message": {"type": "assistant-request"}})
    assert r.status_code == 503
    detail = r.json().get("detail")
    assert isinstance(detail, dict)
    assert detail.get("error") == "webhook_secret_not_configured"


def test_vapi_webhook_rejects_stale_body_timestamp(monkeypatch):
    from backend.routers import voice_router

    secret = b"skew-test"
    monkeypatch.setattr(voice_router, "VAPI_WEBHOOK_SECRET", secret.decode())
    body = {
        "message": {
            "type": "assistant-request",
            "createdAt": "1970-01-01T00:00:00.000Z",
        }
    }
    raw = json.dumps(body).encode()
    sig = hmac.new(secret, raw, hashlib.sha256).hexdigest()
    r = client.post(
        "/vapi-webhook",
        content=raw,
        headers={"X-Vapi-Signature": sig, "Content-Type": "application/json"},
    )
    assert r.status_code == 401


def test_vapi_webhook_requires_timestamp_when_configured(monkeypatch):
    from backend.routers import voice_router

    secret = b"ts-req"
    monkeypatch.setattr(voice_router, "VAPI_WEBHOOK_SECRET", secret.decode())
    monkeypatch.setattr(voice_router, "VAPI_WEBHOOK_REQUIRE_TIMESTAMP", True)
    body = {"message": {"type": "assistant-request"}}
    raw = json.dumps(body).encode()
    sig = hmac.new(secret, raw, hashlib.sha256).hexdigest()
    r = client.post(
        "/vapi-webhook",
        content=raw,
        headers={"X-Vapi-Signature": sig, "Content-Type": "application/json"},
    )
    assert r.status_code == 401


def test_vapi_webhook_duplicate_signed_body_idempotent(monkeypatch):
    from datetime import datetime, timezone

    from backend.routers import voice_router

    secret = b"dedupe-test"
    monkeypatch.setattr(voice_router, "VAPI_WEBHOOK_SECRET", secret.decode())
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    body_dict = {"message": {"type": "assistant-request", "createdAt": now}}
    raw = json.dumps(body_dict, separators=(",", ":")).encode()
    sig = hmac.new(secret, raw, hashlib.sha256).hexdigest()
    headers = {"X-Vapi-Signature": sig, "Content-Type": "application/json"}
    r1 = client.post("/vapi-webhook", content=raw, headers=headers)
    r2 = client.post("/vapi-webhook", content=raw, headers=headers)
    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r1.json() == r2.json()


def test_vapi_webhook_signed_invalid_json_400(monkeypatch):
    from backend.routers import voice_router

    secret = b"sig-secret"
    monkeypatch.setattr(voice_router, "VAPI_WEBHOOK_SECRET", secret.decode())
    raw = b"{broken"
    sig = hmac.new(secret, raw, hashlib.sha256).hexdigest()
    r = client.post(
        "/vapi-webhook",
        content=raw,
        headers={"X-Vapi-Signature": sig, "Content-Type": "application/json"},
    )
    assert r.status_code == 400
