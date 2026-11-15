"""Negotiation cycle between Mobility route proposals and Incidents constraints.

Implements the multi-turn negotiation loop specified in
implementations/01_agenti_negoziazione/03_ciclo_negoziazione.md
and informed by research in ricerca1 and ricerca2.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Any, Protocol

from app.domain.logic.refs import compute_proposal_signature
from app.domain.models.routing import (
    LineTarget,
    NegotiationOutcome,
    Rejection,
    RouteLeg,
    RouteProposal,
    SegmentTarget,
    StopTarget,
    TravelConstraint,
    ZoneTarget,
)
from app.domain.models.trace import Trace
from app.domain.models.trip_request import TripRequest


class NoRouteAvailable(Exception):
    """Raised when the routing planner cannot generate any itineraries."""


class RoutePlanner(Protocol):
    """Protocol for generating route proposals given request and engine constraints."""

    def plan(
        self,
        request: TripRequest,
        constraints: Sequence[TravelConstraint],
        num_itineraries: int = 12,
    ) -> list[RouteProposal]: ...


class RouteValidator(Protocol):
    """Protocol for validating a route proposal and returning applicable constraints."""

    def validate(
        self,
        proposal: RouteProposal,
        ctx: Any = None,
    ) -> list[TravelConstraint]: ...


def translate_constraints(
    constraints: Sequence[TravelConstraint],
    now: datetime | None = None,
) -> tuple[list[TravelConstraint], list[TravelConstraint]]:
    """Partition constraints into (engine_constraints, post_filter_constraints).

    Applies the rule from 03_ciclo_negoziazione.md §5.2-5.3:
    - Anything valid for the whole request goes to the engine.
    - Direction-specific and partial time-window constraints are filtered downstream.
    """
    engine: list[TravelConstraint] = []
    post_filter: list[TravelConstraint] = []

    for c in constraints:
        # Penalty with window that does not contain now is discarded
        if c.kind == "penalty":
            if c.window.from_at is not None or c.window.to_at is not None:
                if now is not None and not c.window.contains(now):
                    continue

        if c.applies_at == "post_filter":
            post_filter.append(c)
            continue

        has_partial_window = c.window.from_at is not None or c.window.to_at is not None
        has_specific_direction = c.direction in ("inbound", "outbound")

        if has_specific_direction or (
            has_partial_window and isinstance(c.target, (LineTarget, StopTarget, SegmentTarget))
        ):
            # Mark as post_filter
            pf = c.model_copy(update={"applies_at": "post_filter"})
            post_filter.append(pf)
        else:
            engine.append(c)

    return engine, post_filter


def _leg_matches_target(leg: RouteLeg, target: Any) -> bool:
    if isinstance(target, LineTarget):
        return leg.route_id is not None and leg.route_id == target.route_id
    if isinstance(target, StopTarget):
        return target.stop_id in (leg.from_stop_id, leg.to_stop_id, leg.from_stop, leg.to_stop)
    if isinstance(target, ZoneTarget):
        return target.zone_id in leg.zone_ids
    if isinstance(target, SegmentTarget):
        route_ok = leg.route_id == target.route_id
        stops_ok = (leg.from_stop_id == target.from_stop or leg.from_stop == target.from_stop) and (
            leg.to_stop_id == target.to_stop or leg.to_stop == target.to_stop
        )
        return route_ok and stops_ok
    return False


def _leg_matches_direction(leg: RouteLeg, direction: str | None) -> bool:
    if not direction or direction == "both":
        return True
    if not leg.headsign:
        return True
    hs = leg.headsign.lower()
    if direction == "inbound" and any(k in hs for k in ("centro", "garibaldi", "inbound")):
        return True
    if direction == "outbound" and any(k in hs for k in ("pozzuoli", "torregaveta", "outbound")):
        return True
    return False


def post_filter_proposals(
    proposals: list[RouteProposal],
    post_constraints: Sequence[TravelConstraint],
) -> list[RouteProposal]:
    """Filter and re-rank proposals based on post_filter constraints."""
    if not post_constraints:
        return proposals

    closure_constraints = [c for c in post_constraints if c.kind == "closure"]
    penalty_constraints = [c for c in post_constraints if c.kind == "penalty"]

    survivors: list[RouteProposal] = []
    for proposal in proposals:
        blocked = False
        for c in closure_constraints:
            for leg in proposal.legs:
                target_hit = _leg_matches_target(leg, c.target)
                window_hit = c.window.overlaps(leg.departure, leg.arrival)
                direction_hit = _leg_matches_direction(leg, c.direction)
                if target_hit and window_hit and direction_hit:
                    blocked = True
                    break
            if blocked:
                break
        if not blocked:
            survivors.append(proposal)

    if not penalty_constraints or not survivors:
        return survivors

    # Re-rank: proposals hit by penalties are ordered after unpenalized proposals
    unpenalized: list[RouteProposal] = []
    penalized: list[RouteProposal] = []

    for prop in survivors:
        is_hit = False
        for c in penalty_constraints:
            for leg in prop.legs:
                target_hit = _leg_matches_target(leg, c.target)
                window_hit = c.window.overlaps(leg.departure, leg.arrival)
                direction_hit = _leg_matches_direction(leg, c.direction)
                if target_hit and window_hit and direction_hit:
                    is_hit = True
                    break
            if is_hit:
                break
        if is_hit:
            penalized.append(prop.model_copy(update={"penalty_applied": True}))
        else:
            unpenalized.append(prop)

    return unpenalized + penalized


def negotiate(
    request: TripRequest,
    planner: RoutePlanner,
    validator: RouteValidator,
    *,
    known_constraints: Sequence[TravelConstraint] = (),
    max_iterations: int = 3,
    num_itineraries: int = 12,
    trace: Trace | None = None,
    now: datetime | None = None,
    ctx: Any = None,
) -> NegotiationOutcome:
    """Execute the multi-turn negotiation cycle between planner and validator."""
    active_constraints: list[TravelConstraint] = list(known_constraints)
    rejected_list: list[Rejection] = []
    applied_refs: set[str] = set()

    # Preload initial constraints references
    for c in known_constraints:
        applied_refs.add(c.evidence_ref)

    last_signature: str | None = None
    candidate_proposal: RouteProposal | None = None
    exhausted = False
    uncertain = False
    final_iteration = 1

    for iteration in range(1, max_iterations + 1):
        final_iteration = iteration

        # 1. Translate constraints
        engine_c, post_c = translate_constraints(active_constraints, now=now)

        # 2. Plan itineraries
        try:
            proposals = planner.plan(request, engine_c, num_itineraries=num_itineraries)
        except (NoRouteAvailable, ValueError):
            proposals = []

        if not proposals:
            exhausted = True
            break

        # 3. Post-filter itineraries
        filtered = post_filter_proposals(proposals, post_c)
        if not filtered:
            # Fallback: if post-filter emptied the list, convert post-filters to gross exclusions
            # or terminate exhausted
            exhausted = True
            candidate_proposal = proposals[0]
            break

        candidate_proposal = filtered[0]
        sig = compute_proposal_signature(candidate_proposal)

        if trace is not None:
            trace.route_proposed(
                proposal_id=candidate_proposal.proposal_id,
                iteration=iteration,
                route_ids=candidate_proposal.route_ids,
                duration_min=candidate_proposal.total_duration_min,
            )

        # 4. Check for loop progress (identical proposal)
        if last_signature is not None and sig == last_signature:
            exhausted = True
            break
        last_signature = sig

        # 5. Validate proposal
        feedback = validator.validate(candidate_proposal, ctx=ctx)
        closures = [c for c in feedback if c.kind == "closure"]
        penalties = [c for c in feedback if c.kind == "penalty"]
        uncertainties = [c for c in feedback if c.kind == "uncertainty"]

        for c in feedback:
            applied_refs.add(c.evidence_ref)

        if uncertainties:
            uncertain = True

        # If only penalties or uncertainty, or no constraints: acceptance!
        if not closures:
            if penalties:
                candidate_proposal = candidate_proposal.model_copy(update={"penalty_applied": True})
            break

        # Route is blocked by closures: reject and loop with new exclusions
        rejected_list.append(
            Rejection(
                proposal_id=candidate_proposal.proposal_id,
                iteration=iteration,
                constraints=tuple(closures),
            )
        )

        if trace is not None:
            trace.route_invalidated(
                proposal_id=candidate_proposal.proposal_id,
                iteration=iteration,
                constraint_kinds=[c.kind for c in closures],
                evidence_refs=[c.evidence_ref for c in closures],
            )

        # Add new closures to active constraints avoiding duplicate evidence_ref
        existing_evidence = {c.evidence_ref for c in active_constraints}
        new_closures = [c for c in closures if c.evidence_ref not in existing_evidence]
        if not new_closures:
            exhausted = True
            break

        active_constraints.extend(new_closures)

        if iteration == max_iterations:
            exhausted = True

    if candidate_proposal is None:
        raise NoRouteAvailable("Nessuna proposta di itinerario disponibile")

    sorted_applied = tuple(sorted(applied_refs))

    if trace is not None:
        trace.negotiation_finished(
            iterations=final_iteration,
            exhausted=exhausted,
            constraints_applied=sorted_applied,
        )

    return NegotiationOutcome(
        final_proposal=candidate_proposal,
        iterations=final_iteration,
        rejected=tuple(rejected_list),
        exhausted=exhausted,
        uncertain=uncertain,
        constraints_applied=sorted_applied,
    )
