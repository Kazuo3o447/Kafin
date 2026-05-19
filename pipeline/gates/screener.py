from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class ScreenerReport:
    passed: bool
    checks: dict[str, bool]
    fail_reasons: list[str] = field(default_factory=list)
    status: str = "screener_complete"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class TradeScreener:
    def __init__(self, min_dollar_volume: float = 5_000_000, max_spread_pct: float = 0.5):
        self.min_dollar_volume = min_dollar_volume
        self.max_spread_pct = max_spread_pct

    def run(self, card: dict[str, Any], snapshot: dict[str, Any], market_regime: str) -> ScreenerReport:
        metrics = snapshot.get("metrics", {})
        checks = {
            "average_daily_volume": _gt(metrics.get("average_daily_dollar_volume_30d"), self.min_dollar_volume),
            "bid_ask_spread": _lt(metrics.get("bid_ask_spread_pct"), self.max_spread_pct),
            "market_cap": _gt(metrics.get("market_cap_usd"), 500_000_000),
            "price": _gt(metrics.get("price"), 5),
            "sma_200_trending_up": bool(metrics.get("sma_200_trending_up")),
            "recent_52_week_high": _lte(metrics.get("days_since_52w_high"), 90),
            "earnings_not_imminent": _gt(metrics.get("trading_days_to_earnings"), 5),
            "plain_equity_or_etf": metrics.get("instrument_type", "equity") in {"equity", "etf"}
            and not bool(metrics.get("is_leveraged"))
            and not bool(metrics.get("is_derivative")),
            "market_regime": market_regime not in {"risk_off", "panic"},
            "research_handoff": bool(card.get("handoff_to_trade_engine")),
        }
        fail_reasons = [name for name, passed in checks.items() if not passed]
        return ScreenerReport(passed=not fail_reasons, checks=checks, fail_reasons=fail_reasons)


def _num(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _gt(value: Any, threshold: float) -> bool:
    numeric = _num(value)
    return numeric is not None and numeric > threshold


def _lt(value: Any, threshold: float) -> bool:
    numeric = _num(value)
    return numeric is not None and numeric < threshold


def _lte(value: Any, threshold: float) -> bool:
    numeric = _num(value)
    return numeric is not None and numeric <= threshold
