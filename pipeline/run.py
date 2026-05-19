from __future__ import annotations

import argparse
import json
from pathlib import Path

from pipeline.config import PlatformConfig
from pipeline.graph import run_pipeline


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the local research pipeline.")
    parser.add_argument("ticker", help="Ticker symbol, e.g. NVDA")
    parser.add_argument("--phase", type=int, default=None, help="Override PLATFORM_PHASE")
    parser.add_argument("--project-root", default=".", help="Repository root")
    args = parser.parse_args()

    config = PlatformConfig.from_env(project_root=Path(args.project_root), phase=args.phase)
    state = run_pipeline(args.ticker, config=config)
    print(json.dumps({"run_id": state["run_id"], "status": state["status"]}, indent=2))


if __name__ == "__main__":
    main()
