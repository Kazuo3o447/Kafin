from __future__ import annotations

import argparse
import json
from pathlib import Path

from data.sources.intelligence_adapter import MultiSourceSnapshotBuilder, build_filter_queue_entries


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch a minimal local market snapshot.")
    parser.add_argument("ticker", nargs="?")
    parser.add_argument("--out", default="data/snapshots")
    parser.add_argument("--watchlist", action="store_true", help="Fetch all watchlist tickers plus market context")
    args = parser.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    builder = MultiSourceSnapshotBuilder()
    market_snapshot = builder.fetch_market_snapshot()
    market_target = out_dir / "_MARKET.json"
    market_target.write_text(json.dumps(market_snapshot, indent=2, sort_keys=True), encoding="utf-8")

    tickers: list[str]
    if args.watchlist:
        watchlist = _read_watchlist(Path("research/watchlist.json"))
        tickers = [item["ticker"] for item in watchlist]
    elif args.ticker:
        tickers = [args.ticker.upper()]
        watchlist = [{"ticker": args.ticker.upper(), "note": None}]
    else:
        raise SystemExit("Provide a ticker or use --watchlist")

    snapshots: dict[str, dict[str, object]] = {}
    for ticker in tickers:
        snapshot = builder.fetch_snapshot(ticker, market_snapshot=market_snapshot)
        snapshots[ticker.upper()] = snapshot
        target = out_dir / f"{ticker.upper()}.json"
        target.write_text(json.dumps(snapshot, indent=2, sort_keys=True), encoding="utf-8")
        print(target)

    filter_queue = build_filter_queue_entries(watchlist, snapshots, market_snapshot)
    queue_path = Path("research/filter_queue.json")
    queue_path.write_text(json.dumps(filter_queue, indent=2, sort_keys=True), encoding="utf-8")
    print(queue_path)


def _read_watchlist(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
