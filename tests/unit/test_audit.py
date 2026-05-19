from __future__ import annotations

from pipeline.audit import JsonlAuditLogger, load_audit_events


def test_jsonl_audit_roundtrip(tmp_path):
    logger = JsonlAuditLogger(tmp_path / "audit")
    logger.log("run-1", "started", {"ticker": "NVDA"})
    logger.log("run-1", "finished", {"status": "ok"})

    events = load_audit_events("run-1", tmp_path / "audit")

    assert [event["event_type"] for event in events] == ["started", "finished"]
    assert events[0]["payload"]["ticker"] == "NVDA"
