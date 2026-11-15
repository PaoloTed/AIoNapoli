"""Base connector interface and normalized execution outcome."""

from __future__ import annotations

from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict


class ConnectorOutcome(BaseModel):
    """Structured outcome returned by every connector run or fallback."""

    model_config = ConfigDict(extra="forbid")

    connector: str
    source_id: str
    rows_written: int
    is_simulated: bool
    outcome: Literal["ok", "fallback", "failed"]
    detail: str


class BaseConnector(Protocol):
    """Common contract exposed by all five ingestion connectors."""

    source_id: str
    frequency: str

    def run(self) -> ConnectorOutcome:
        """Execute normal ingestion with automatic fallback on external failure."""
        ...

    def fallback(self, reason: str = "manual_fallback") -> ConnectorOutcome:
        """Execute declared simulated fallback and persist is_simulated=True rows."""
        ...
