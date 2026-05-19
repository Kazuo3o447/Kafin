from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, NotRequired, TypedDict
from uuid import uuid4


class PipelineState(TypedDict):
    ticker: str
    run_id: str
    started_at: str
    phase: int
    data_snapshot: NotRequired[dict[str, Any]]
    card: NotRequired[dict[str, Any]]
    redteam: NotRequired[dict[str, Any]]
    screener: NotRequired[dict[str, Any]]
    risk: NotRequired[dict[str, Any]]
    status: str
    errors: list[str]


def new_state(ticker: str, phase: int) -> PipelineState:
    return {
        "ticker": ticker.upper(),
        "run_id": uuid4().hex,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "phase": phase,
        "status": "started",
        "errors": [],
    }
