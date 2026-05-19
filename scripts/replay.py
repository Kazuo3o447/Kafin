from __future__ import annotations

import argparse
import json
from pathlib import Path

from pipeline.audit import load_audit_events
from pipeline.config import PlatformConfig
from pipeline.graph import run_pipeline


def main() -> None:
    parser = argparse.ArgumentParser(description="Replay audit metadata for a previous run.")
    parser.add_argument("run_id")
    parser.add_argument("--audit-dir", default="audit")
    args = parser.parse_args()

    events = load_audit_events(args.run_id, Path(args.audit_dir))
    if not events:
        raise SystemExit(f"run not found: {args.run_id}")

    started = next((event for event in events if event["event_type"] == "run_started"), None)
    if not started:
        raise SystemExit(f"run has no run_started event: {args.run_id}")

    ticker = started["payload"]["ticker"]
    phase = int(started["payload"]["phase"])
    replay_state = run_pipeline(ticker, PlatformConfig.from_env(phase=phase))
    replay_events = load_audit_events(replay_state["run_id"], Path(args.audit_dir))

    original_types = [event["event_type"] for event in events]
    replay_types = [event["event_type"] for event in replay_events]
    summary = {
        "run_id": args.run_id,
        "replay_run_id": replay_state["run_id"],
        "event_count": len(events),
        "first_event": events[0]["event_type"],
        "last_event": events[-1]["event_type"],
        "event_types_match": original_types == replay_types,
        "original_event_types": original_types,
        "replay_event_types": replay_types,
        "token_tolerance": "5%",
    }
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
