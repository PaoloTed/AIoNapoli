"""Regression tests for the MobilityAgent -> OtpClient mode contract."""

from __future__ import annotations

from typing import Any

from app.domain.models.finding import Finding
from app.repositories.memory import InMemorySourceRepository
from app.services.agents.mobility.agent import MobilityAgent
from app.services.agents.mobility.otp_client import (
    DEFAULT_MODES,
    ItineraryPlan,
    ItineraryResult,
)


class _SpyOtp:
    mode = "real"

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def plan_itineraries(self, **kwargs: Any) -> ItineraryPlan:
        self.calls.append(kwargs)
        return ItineraryPlan(
            itineraries=[
                ItineraryResult(
                    start="2026-11-16T08:00:00+01:00",
                    end="2026-11-16T08:20:00+01:00",
                    duration_s=1200,
                    walk_time_s=300,
                    walk_distance_m=250.0,
                    transfers=0,
                    generalized_cost=None,
                    legs=[],
                )
            ],
            routing_errors=[],
            is_simulated=False,
            source_id="otp",
            data_reference="http://otp.test/otp/gtfs/v1",
        )


def test_default_modes_include_subway() -> None:
    assert "SUBWAY" in DEFAULT_MODES
    assert "BUS" in DEFAULT_MODES
    assert "RAIL" in DEFAULT_MODES


def test_agent_passes_the_single_default_modes_tuple() -> None:
    """The agent must not keep a second, drifting copy of the mode list."""
    spy = _SpyOtp()
    agent = MobilityAgent(
        InMemorySourceRepository(load_fixtures=True),
        otp_client=spy,  # type: ignore[arg-type]
    )

    result = agent.evaluate(
        route_id="L2",
        origin_stop_id="STOP_GAR_01",
        destination_stop_id="STOP_BAG_01",
    )

    assert isinstance(result, Finding)
    assert len(spy.calls) == 1
    assert spy.calls[0]["modes"] is DEFAULT_MODES
    assert "SUBWAY" in spy.calls[0]["modes"]
