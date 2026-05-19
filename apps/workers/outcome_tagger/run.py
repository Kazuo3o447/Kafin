from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Attach manual outcome placeholders to cards.")
    parser.add_argument("--cards-dir", default="research/cards")
    args = parser.parse_args()

    updated = 0
    for path in Path(args.cards_dir).glob("*.json"):
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload.setdefault("outcome", {"status": "unknown", "checked_at": date.today().isoformat()})
        path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        updated += 1
    print(json.dumps({"updated": updated}))


if __name__ == "__main__":
    main()
