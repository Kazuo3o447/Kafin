from __future__ import annotations

import json
from pathlib import Path
from typing import Any


REQUIRED_CARD_FIELDS = [
    "revenue_5y",
    "revenue_growth_5y",
    "gross_margin_5y",
    "operating_margin_5y",
    "fcf_margin_5y",
    "roic",
    "net_debt_to_ebitda",
    "share_count_trend_3y",
    "sbc_to_revenue",
    "sbc_to_ocf",
    "forward_pe",
    "ev_to_sales",
    "ev_to_gross_profit",
    "week_52_high",
    "sma_200",
    "sma_50",
    "average_daily_volume_30d",
    "next_earnings_date",
    "last_earnings_surprise",
]


def load_snapshot(ticker: str, snapshots_dir: Path) -> dict[str, Any]:
    path = snapshots_dir / f"{ticker.upper()}.json"
    if not path.exists():
        return {
            "ticker": ticker.upper(),
            "metrics": {},
            "sources": [],
            "quality_errors": [f"snapshot missing: {path}"],
        }
    return json.loads(path.read_text(encoding="utf-8"))


def get_company_metrics(ticker: str, snapshots_dir: Path) -> dict[str, Any]:
    snapshot = load_snapshot(ticker, snapshots_dir)
    return snapshot.get("metrics", {})


def missing_required_fields(snapshot: dict[str, Any]) -> list[str]:
    metrics = snapshot.get("metrics", {})
    return [field for field in REQUIRED_CARD_FIELDS if metrics.get(field) in (None, "", "unknown")]


def write_rejection(ticker: str, reason: str, rejected_dir: Path) -> Path:
    rejected_dir.mkdir(parents=True, exist_ok=True)
    path = rejected_dir / f"{ticker.upper()}_rejected.json"
    payload = {"ticker": ticker.upper(), "reason": reason}
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return path
