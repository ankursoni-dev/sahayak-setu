"""Unit tests for Vapi webhook guard helpers."""

from backend.services.vapi_webhook_guard import (
    extract_webhook_delivery_id,
    _webhook_dedupe_material,
)


def test_extract_delivery_id_nested_call():
    p = {"message": {"type": "status-update", "call": {"id": "call-abc-123"}}}
    assert extract_webhook_delivery_id(p) == "call-abc-123"


def test_extract_delivery_id_top_level():
    p = {"id": "evt-1", "message": {}}
    assert extract_webhook_delivery_id(p) == "evt-1"


def test_extract_delivery_id_call_id_flat():
    p = {"message": {"callId": "flat-99"}}
    assert extract_webhook_delivery_id(p) == "flat-99"


def test_dedupe_material_includes_id_when_present():
    body = b'{"message":{"call":{"id":"c1"}}}'
    p = {"message": {"call": {"id": "c1"}}}
    m1 = _webhook_dedupe_material(p, body)
    p2 = {"message": {"call": {"id": "c2"}}}
    m2 = _webhook_dedupe_material(p2, body)
    assert m1 != m2
