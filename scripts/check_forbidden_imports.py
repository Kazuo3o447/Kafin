from __future__ import annotations

import ast
import sys
from pathlib import Path


FORBIDDEN_IMPORTS = {
    "alpaca",
    "alpaca_trade_api",
    "ccxt",
    "ibapi",
    "ib_insync",
    "interactivebrokers",
    "binance",
    "coinbase",
}

IGNORED_DIRS = {".git", ".venv", "__pycache__", ".pytest_cache", ".ruff_cache"}


def main(root: Path | None = None) -> None:
    root = root or (Path(sys.argv[1]) if len(sys.argv) > 1 else Path("."))
    violations: list[str] = []
    for path in _python_files(root):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError as exc:
            violations.append(f"{path}: syntax error: {exc}")
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    _check(alias.name, path, violations)
            elif isinstance(node, ast.ImportFrom) and node.module:
                _check(node.module, path, violations)

    if violations:
        print("Forbidden trading imports found:")
        for violation in violations:
            print(f"- {violation}")
        raise SystemExit(1)


def _python_files(root: Path) -> list[Path]:
    files = []
    for path in root.rglob("*.py"):
        if any(part in IGNORED_DIRS for part in path.parts):
            continue
        files.append(path)
    return files


def _check(module: str, path: Path, violations: list[str]) -> None:
    top_level = module.split(".", 1)[0].lower()
    if top_level in FORBIDDEN_IMPORTS:
        violations.append(f"{path}: import {module}")


if __name__ == "__main__":
    main()
