from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class JournalAgent:
    def __init__(self, journal_dir: Path):
        self.journal_dir = journal_dir

    def record(self, card_ref: str, event: str, reason: str, rule: str, payload: dict[str, Any]) -> Path:
        self.journal_dir.mkdir(parents=True, exist_ok=True)
        now = datetime.now(timezone.utc)
        path = self.journal_dir / f"{now.date().isoformat()}.md"
        entry = f"""
## {now.isoformat()}

- Card-Referenz: {card_ref}
- Was ist passiert: {event}
- Begruendung: {reason}
- Relevante Regel: {rule}
- Annahme: {payload.get('assumption', 'unknown')}
- Ueberraschung: {payload.get('surprise', 'none')}
"""
        with path.open("a", encoding="utf-8") as handle:
            handle.write(entry)
        return path
