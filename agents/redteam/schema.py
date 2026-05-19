from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path


@dataclass
class RedTeamReport:
    ticker: str
    report_date: str = field(default_factory=lambda: date.today().isoformat())
    weakest_assumptions: list[str] = field(default_factory=list)
    disqualifiers: list[str] = field(default_factory=list)
    weak_evidence: list[str] = field(default_factory=list)
    recommendation: str = "revise"
    status: str = "redteam_complete"

    def to_dict(self) -> dict:
        return asdict(self)

    def to_markdown(self) -> str:
        return f"""# Red-Team Report: {self.ticker}

## Schwaechste Annahmen
{_format_list(self.weakest_assumptions)}

## Disqualifier
{_format_list(self.disqualifiers)}

## Schwache Belege
{_format_list(self.weak_evidence)}

## Empfehlung
{self.recommendation}
"""

    def write_files(self, cards_dir: Path) -> tuple[Path, Path]:
        cards_dir.mkdir(parents=True, exist_ok=True)
        stem = f"{self.ticker.upper()}_{self.report_date}_redteam"
        markdown_path = cards_dir / f"{stem}.md"
        json_path = cards_dir / f"{stem}.json"
        markdown_path.write_text(self.to_markdown(), encoding="utf-8")
        json_path.write_text(json.dumps(self.to_dict(), indent=2, sort_keys=True), encoding="utf-8")
        return markdown_path, json_path


def _format_list(values: list[str]) -> str:
    if not values:
        return "- none"
    return "\n".join(f"- {value}" for value in values)
