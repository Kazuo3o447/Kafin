from __future__ import annotations

from pipeline.config import PlatformConfig
from pipeline.graph import run_pipeline


def test_phase_zero_pipeline_writes_audit(tmp_path):
    config = PlatformConfig.from_env(project_root=tmp_path, phase=0)
    state = run_pipeline("NVDA", config=config)

    assert state["status"] == "research_complete"
    assert list((tmp_path / "audit").glob("*/*.jsonl"))
