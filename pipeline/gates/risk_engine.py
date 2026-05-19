from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class RiskReport:
    status: str
    position_size_eur: float = 0.0
    position_size_pct: float = 0.0
    stop_price: float = 0.0
    stop_pct: float = 0.0
    targets: dict[str, float] = field(default_factory=dict)
    fail_reasons: list[str] = field(default_factory=list)
    rationale: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class RiskEngine:
    def run(self, snapshot: dict[str, Any]) -> RiskReport:
        metrics = snapshot.get("metrics", {})
        account_value = _num(metrics.get("paper_account_value_eur"), 10_000)
        risk_pct = min(max(_num(metrics.get("risk_per_trade_pct"), 0.25), 0.0), 0.5)
        entry = _num(metrics.get("entry_price"), _num(metrics.get("price"), 0.0))
        atr = _num(metrics.get("atr_14"), 0.0)
        stop_price = _num(metrics.get("proposed_stop_price"), entry - 2.0 * atr)

        fail_reasons = []
        if entry <= 0:
            fail_reasons.append("entry_price_missing")
        if atr <= 0:
            fail_reasons.append("atr_missing")
        if stop_price >= entry:
            fail_reasons.append("stop_not_below_entry")

        stop_distance = entry - stop_price
        if atr > 0 and stop_distance > 2.5 * atr:
            fail_reasons.append("stop_looser_than_atr_rule")

        risk_eur = account_value * (risk_pct / 100)
        shares = risk_eur / stop_distance if stop_distance > 0 else 0.0
        position_value = shares * entry
        position_pct = (position_value / account_value) * 100 if account_value else 0.0
        if position_pct > 10:
            fail_reasons.append("position_allocation_above_10_pct")

        targets = {
            "r1": entry + stop_distance,
            "r2": entry + 2 * stop_distance,
            "r3": entry + 3 * stop_distance,
        }
        return RiskReport(
            status="risk_blocked" if fail_reasons else "risk_ok",
            position_size_eur=round(position_value, 2),
            position_size_pct=round(position_pct, 2),
            stop_price=round(stop_price, 2),
            stop_pct=round((stop_distance / entry) * 100, 2) if entry else 0.0,
            targets={key: round(value, 2) for key, value in targets.items()},
            fail_reasons=fail_reasons,
            rationale=(
                "Positionsgroesse wird aus Depotwert, Risiko pro Trade und Stop-Abstand berechnet. "
                "Die Berechnung darf Score oder Ueberzeugung nicht zur Risikoerhoehung nutzen."
            ),
        )


def _num(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default
