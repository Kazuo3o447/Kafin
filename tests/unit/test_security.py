from __future__ import annotations

from pathlib import Path

from scripts.check_forbidden_imports import main


def test_forbidden_import_checker_passes_repo():
    main(Path("."))
