from __future__ import annotations

from datetime import date, datetime
from typing import Any


def validate_snapshot_quality(snapshot: dict[str, Any], max_age_days: int = 7) -> list[str]:
    errors: list[str] = []
    as_of = snapshot.get("as_of")
    if as_of:
        try:
            age = (date.today() - datetime.fromisoformat(str(as_of)).date()).days
            if age > max_age_days:
                errors.append(f"snapshot_stale:{age}d")
        except ValueError:
            errors.append("snapshot_as_of_invalid")
    else:
        errors.append("snapshot_as_of_missing")

    metrics = snapshot.get("metrics", {})
    if _num(metrics.get("gross_margin_5y")) is not None and _num(metrics.get("gross_margin_5y")) < -1:
        errors.append("gross_margin_implausible")
    if _num(metrics.get("roic")) is not None and _num(metrics.get("roic")) > 10:
        errors.append("roic_implausible")
    if _num(metrics.get("sbc_to_revenue")) is not None and _num(metrics.get("sbc_to_revenue")) > 1:
        errors.append("sbc_to_revenue_implausible")
    return errors


def _num(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
