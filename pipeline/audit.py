from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass
class AuditEvent:
    run_id: str
    event_type: str
    payload: dict[str, Any]
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_json(self) -> str:
        return json.dumps(asdict(self), sort_keys=True)


class JsonlAuditLogger:
    def __init__(self, audit_dir: Path):
        self.audit_dir = audit_dir

    def log(self, run_id: str, event_type: str, payload: dict[str, Any]) -> AuditEvent:
        event = AuditEvent(run_id=run_id, event_type=event_type, payload=payload)
        month = event.timestamp[:7]
        directory = self.audit_dir / month
        directory.mkdir(parents=True, exist_ok=True)
        with (directory / f"{run_id}.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(event.to_json() + "\n")
        return event


def load_audit_events(run_id: str, audit_dir: Path) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    if not audit_dir.exists():
        return events
    for path in audit_dir.glob(f"*/{run_id}.jsonl"):
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                events.append(json.loads(line))
    return sorted(events, key=lambda event: event["timestamp"])
