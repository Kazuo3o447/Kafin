from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agents.journal.agent import JournalAgent
from agents.redteam.agent import RedTeamAgent
from agents.research.agent import ResearchAgent
from agents.research.tools import load_snapshot, missing_required_fields, write_rejection
from pipeline.audit import JsonlAuditLogger
from pipeline.config import PlatformConfig
from pipeline.gates.execution_gatekeeper import ExecutionGatekeeper
from pipeline.gates.risk_engine import RiskEngine
from pipeline.gates.screener import TradeScreener
from pipeline.state import PipelineState, new_state


def run_pipeline(ticker: str, config: PlatformConfig | None = None) -> PipelineState:
    config = config or PlatformConfig.from_env()
    state = new_state(ticker, config.phase)
    audit = JsonlAuditLogger(config.audit_dir)
    journal = JournalAgent(config.journal_dir)

    audit.log(state["run_id"], "run_started", {"ticker": state["ticker"], "phase": config.phase})

    try:
        if config.phase == 0:
            _run_phase_zero(state, audit)
            return state

        snapshot = load_snapshot(state["ticker"], config.snapshots_dir)
        state["data_snapshot"] = snapshot
        audit.log(
            state["run_id"],
            "data_loaded",
            {"quality_errors": snapshot.get("quality_errors", []), "snapshot": snapshot},
        )

        missing = missing_required_fields(snapshot)
        if missing:
            reason = f"missing required fields: {', '.join(missing)}"
            rejection_path = write_rejection(state["ticker"], reason, config.rejected_dir)
            state["status"] = "data_rejected"
            state["errors"].append(reason)
            audit.log(state["run_id"], "data_rejected", {"reason": reason, "path": str(rejection_path)})
            journal.record(
                card_ref=state["ticker"],
                event="Ticker blockiert, keine Research Card erzeugt.",
                reason=reason,
                rule="Agent.md Abschnitt 8.3",
                payload={"assumption": "Pflichtfelder muessen vor Card-Erzeugung vorliegen."},
            )
            return state

        card = ResearchAgent(allow_llm=config.allow_llm, evidence_dir=config.evidence_dir).run(state["ticker"], snapshot)
        markdown_path, json_path = card.write_files(config.cards_dir)
        state["card"] = card.to_dict()
        state["status"] = card.status
        if card.llm_metadata:
            audit.log(state["run_id"], "llm_usage_recorded", card.llm_metadata)
        audit.log(
            state["run_id"],
            "research_complete",
            {
                "markdown_path": str(markdown_path),
                "json_path": str(json_path),
                "score": card.growth_research_score,
                "llm_metadata": card.llm_metadata,
                "card": card.to_dict(),
            },
        )

        redteam = RedTeamAgent().run(card)
        red_markdown, red_json = redteam.write_files(config.cards_dir)
        state["redteam"] = redteam.to_dict()
        state["status"] = redteam.status
        audit.log(
            state["run_id"],
            "redteam_complete",
            {
                "markdown_path": str(red_markdown),
                "json_path": str(red_json),
                "recommendation": redteam.recommendation,
                "redteam": redteam.to_dict(),
            },
        )

        screener = TradeScreener().run(card=card.to_dict(), snapshot=snapshot, market_regime=snapshot.get("market_regime", "unknown"))
        state["screener"] = screener.to_dict()
        state["status"] = "screener_passed" if screener.passed else "screener_failed"
        audit.log(state["run_id"], "screener_complete", screener.to_dict())

        if config.phase == 1:
            journal.record(
                card_ref=f"{state['ticker']}:{state['run_id']}",
                event="Research, Red-Team und Screener abgeschlossen. Kein Paper-Trade simuliert.",
                reason="Phase 1 endet gemaess Agent.md nach dem Trade Screener.",
                rule="Agent.md Abschnitt 10.2 und 15",
                payload={"assumption": "Risk Engine und Paper-Simulator sind deaktiviert."},
            )
            return state

        if config.risk_enabled and screener.passed:
            risk = RiskEngine().run(snapshot=snapshot)
            state["risk"] = risk.to_dict()
            state["status"] = "risk_ok" if risk.status == "risk_ok" else "risk_blocked"
            audit.log(state["run_id"], "risk_complete", risk.to_dict())

            gate = ExecutionGatekeeper().run(state=state, phase=config.phase)
            state["status"] = gate["status"]
            audit.log(state["run_id"], "execution_gatekeeper_complete", gate)

        return state
    except Exception as exc:
        state["status"] = "failed"
        state["errors"].append(str(exc))
        audit.log(state["run_id"], "run_failed", {"error": str(exc)})
        _archive_failed_run(state, config.project_root / "failed_runs")
        raise


def _run_phase_zero(state: PipelineState, audit: JsonlAuditLogger) -> None:
    state["data_snapshot"] = {"ticker": state["ticker"], "phase": 0, "metrics": {}, "sources": []}
    audit.log(state["run_id"], "dummy_load_data_complete", {"ticker": state["ticker"]})
    state["card"] = {
        "ticker": state["ticker"],
        "status": "research_complete",
        "message": "Phase-0-Hello-World. No trade, no recommendation, no broker action.",
    }
    state["status"] = "research_complete"
    audit.log(state["run_id"], "dummy_research_complete", state["card"])


def _archive_failed_run(state: PipelineState, failed_dir: Path) -> Path:
    failed_dir.mkdir(parents=True, exist_ok=True)
    path = failed_dir / f"{state['run_id']}.json"
    path.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")
    return path
