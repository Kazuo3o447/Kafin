from __future__ import annotations

from typing import Any


class ExecutionGatekeeper:
    def run(self, state: dict[str, Any], phase: int) -> dict[str, Any]:
        if phase < 2:
            return {
                "status": "gatekeeper_blocked",
                "reason": "Phase erlaubt keinen Risk- oder Paper-Trade-Pfad.",
            }

        required = ["card", "redteam", "screener", "risk"]
        missing = [key for key in required if key not in state]
        if missing:
            return {"status": "gatekeeper_blocked", "reason": "missing prior steps", "missing": missing}

        screener = state["screener"]
        risk = state["risk"]
        if not screener.get("passed"):
            return {"status": "gatekeeper_blocked", "reason": "screener_failed"}
        if risk.get("status") != "risk_ok":
            return {"status": "gatekeeper_blocked", "reason": "risk_blocked"}

        return {"status": "awaiting_human", "reason": "all gates complete; human decision required"}
