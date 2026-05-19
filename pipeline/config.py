from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


load_dotenv()


@dataclass(frozen=True)
class PlatformConfig:
    project_root: Path = Path(".")
    phase: int = 0
    audit_dir: Path = Path("audit")
    snapshots_dir: Path = Path("data/snapshots")
    cards_dir: Path = Path("research/cards")
    evidence_dir: Path = Path("research/evidence")
    rejected_dir: Path = Path("research/rejected")
    journal_dir: Path = Path("journal")
    allow_llm: bool = False

    @classmethod
    def from_env(cls, project_root: Path | None = None, phase: int | None = None) -> "PlatformConfig":
        root = project_root or Path(".")
        env_phase = int(os.getenv("PLATFORM_PHASE", "0"))
        selected_phase = env_phase if phase is None else phase
        default_allow_llm = "true" if os.getenv("DEEPSEEK_API_KEY") else "false"
        return cls(
            project_root=root,
            phase=selected_phase,
            audit_dir=root / os.getenv("AUDIT_DIR", "audit"),
            snapshots_dir=root / "data" / "snapshots",
            cards_dir=root / "research" / "cards",
            evidence_dir=root / "research" / "evidence",
            rejected_dir=root / "research" / "rejected",
            journal_dir=root / "journal",
            allow_llm=os.getenv("ALLOW_LLM", default_allow_llm).lower() == "true",
        )

    @property
    def risk_enabled(self) -> bool:
        return self.phase >= 2
