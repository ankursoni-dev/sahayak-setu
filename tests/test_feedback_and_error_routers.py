"""Contract tests for /api/feedback and /api/error."""

from __future__ import annotations

from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)


def test_feedback_accepts_valid_up_reaction():
    r = client.post(
        "/api/feedback",
        json={
            "value": "up",
            "trace_id": "t-123",
            "session_user_id": "u-abc",
            "query_preview": "pm kisan",
            "answer_preview": "PM Kisan is a DBT scheme.",
        },
    )
    assert r.status_code == 200
    assert r.json() == {"ok": True}


def test_feedback_accepts_valid_down_reaction():
    r = client.post("/api/feedback", json={"value": "down"})
    assert r.status_code == 200


def test_feedback_rejects_invalid_value_422():
    r = client.post("/api/feedback", json={"value": "maybe"})
    assert r.status_code == 422


def test_feedback_rejects_missing_value_422():
    r = client.post("/api/feedback", json={})
    assert r.status_code == 422


def test_error_report_accepted():
    r = client.post(
        "/api/error",
        json={
            "error": "timeout",
            "trace_id": "t-1",
            "language": "hi-IN",
            "query_prefix": "pm kisan",
            "http_status": 504,
        },
    )
    assert r.status_code == 200
    assert r.json() == {"ok": True}


def test_error_report_missing_error_field_422():
    r = client.post("/api/error", json={"trace_id": "t"})
    assert r.status_code == 422


def test_error_report_oversized_error_code_422():
    r = client.post("/api/error", json={"error": "x" * 200})
    assert r.status_code == 422


def test_openapi_schema_exposes_all_routes():
    schema = app.openapi()
    paths = set(schema.get("paths", {}).keys())
    expected = {"/", "/health", "/ping", "/ready", "/api/search", "/api/search/stream", "/api/feedback", "/api/error", "/vapi-webhook"}
    missing = expected - paths
    assert not missing, f"Missing routes in OpenAPI: {missing}"


def test_openapi_info_enriched():
    schema = app.openapi()
    info = schema.get("info", {})
    assert info.get("title") == "SahayakSetu API"
    assert info.get("version") == "1.0.0"
    assert "description" in info and len(info["description"]) > 50
    tags = {t["name"] for t in schema.get("tags", [])}
    assert {"search", "health", "voice", "feedback", "telemetry"}.issubset(tags)
