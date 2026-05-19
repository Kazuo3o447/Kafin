from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CheckpointerConfig:
    table_name: str = "langgraph_checkpoints"
    saver: str = "postgres"


def describe_checkpointer() -> dict[str, str]:
    """Return the intended LangGraph checkpointer contract.

    The actual Postgres saver is wired when the runtime dependencies and database are available.
    Keeping this as a small contract makes Phase 0 runnable without requiring a live database.
    """

    config = CheckpointerConfig()
    return {"saver": config.saver, "table_name": config.table_name}
