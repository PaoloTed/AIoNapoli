"""OpenTripPlanner 2 GTFS GraphQL client with explicit real/demo separation.

Only OTP 2.10's ``/otp/gtfs/v1`` ``planConnection`` contract is used. User
input is sent as GraphQL variables, never concatenated into the query.

Minimal validity rules for a real itinerary:

- at least one leg;
- every leg has a mode, interpretable offset-aware scheduled start/end times,
  non-decreasing times, and usable from/to coordinates;
- every transit leg has route, trip, origin-stop and destination-stop IDs;
- duration is declared coherently or is derived from valid times; declared
  durations must be finite, non-negative and consistent within
  ``TIME_TOLERANCE_S``;
- itinerary start/end, when present, are interpretable and coherent with the
  first/last leg.

Optional fields (route names, estimated times/delays, geometry, stop names,
walkTime/walkDistance, transfers, generalizedCost) may be absent. Missing or
incoherent mandatory fields raise ``OtpInvalidResponseError``; values are not
clamped or corrected.
"""

from __future__ import annotations

import json
import math
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import httpx

from app.services.agents.mobility.gtfs_ids import is_feed_scoped_id, parse_otp_id

OtpMode = Literal["real", "demo"]
TIME_TOLERANCE_S = 2.0
DEFAULT_MODES: tuple[str, ...] = ("WALK", "BUS", "RAIL", "SUBWAY")
DIRECT_MODES = frozenset(
    {
        "BICYCLE",
        "BICYCLE_PARKING",
        "BICYCLE_RENTAL",
        "CAR",
        "CAR_PARKING",
        "CAR_RENTAL",
        "FLEX",
        "SCOOTER_RENTAL",
        "WALK",
    }
)
TRANSIT_MODES = frozenset(
    {
        "AIRPLANE",
        "BUS",
        "CABLE_CAR",
        "CARPOOL",
        "COACH",
        "FERRY",
        "FUNICULAR",
        "GONDOLA",
        "MONORAIL",
        "RAIL",
        "SNOW_AND_ICE",
        "SUBWAY",
        "TAXI",
        "TRAM",
        "TROLLEYBUS",
    }
)

PLAN_QUERY = """query Plan(
  $origin: PlanLabeledLocationInput!,
  $destination: PlanLabeledLocationInput!,
  $dateTime: PlanDateTimeInput,
  $first: Int,
  $modes: PlanModesInput,
  $preferences: PlanPreferencesInput
) {
  planConnection(
    origin: $origin
    destination: $destination
    dateTime: $dateTime
    first: $first
    modes: $modes
    preferences: $preferences
  ) {
    edges {
      node {
        start
        end
        duration
        walkTime
        walkDistance
        numberOfTransfers
        generalizedCost
        legs {
          mode
          transitLeg
          duration
          start { scheduledTime estimated { time delay } }
          end { scheduledTime estimated { time delay } }
          route {
            gtfsId
            shortName
            longName
            mode
            agency { gtfsId name }
          }
          trip { gtfsId }
          from { name lat lon stop { gtfsId name } }
          to { name lat lon stop { gtfsId name } }
          legGeometry { points length }
        }
      }
    }
    routingErrors { code description inputField }
  }
}"""

ROUTES_QUERY = """query Routes {
  routes {
    gtfsId
    shortName
    longName
    mode
    agency { gtfsId name }
  }
}"""

AGENCIES_QUERY = """query Agencies {
  agencies { gtfsId name }
}"""


class OtpError(Exception):
    """Base class for explicit OTP failures."""


class OtpTimeoutError(OtpError):
    """The HTTP request timed out."""


class OtpUnavailableError(OtpError):
    """OTP could not be reached (connection/DNS/network error)."""


class OtpHttpError(OtpError):
    """OTP returned an HTTP error response."""

    def __init__(self, status_code: int, body: str) -> None:
        self.status_code = status_code
        self.body = body[:500]
        super().__init__(f"OTP HTTP {status_code}: {self.body}")


class OtpGraphQLError(OtpError):
    """OTP returned GraphQL errors, possibly with HTTP 200."""

    def __init__(self, errors: list[dict[str, Any]]) -> None:
        self.errors = errors
        messages = "; ".join(str(item.get("message", item)) for item in errors)
        super().__init__(f"OTP GraphQL error: {messages}")


class OtpInvalidResponseError(OtpError):
    """OTP returned JSON that does not match the expected GraphQL shape."""


class OtpNoRouteError(OtpError):
    """OTP returned no usable itinerary."""

    def __init__(
        self,
        routing_errors: list[dict[str, Any]],
        detail: str = "OTP returned no itineraries",
    ) -> None:
        self.routing_errors = routing_errors
        suffixes = [str(item.get("code", "")) for item in routing_errors if item.get("code")]
        if suffixes:
            detail = f"{detail} ({', '.join(suffixes)})"
        super().__init__(detail)


@dataclass(frozen=True)
class ItineraryResult:
    """One normalized OTP itinerary, retaining all useful leg identifiers."""

    start: str | None
    end: str | None
    duration_s: int | None
    walk_time_s: int | None
    walk_distance_m: float | None
    transfers: int | None
    generalized_cost: int | None
    legs: list[dict[str, Any]]
    raw: dict[str, Any] = field(default_factory=dict, repr=False)


@dataclass(frozen=True)
class ItineraryPlan:
    """All itineraries returned by one OTP call, plus non-fatal warnings."""

    itineraries: list[ItineraryResult]
    routing_errors: list[dict[str, Any]]
    is_simulated: bool
    source_id: str
    data_reference: str
    fallback_reason: str | None = None


@dataclass(frozen=True)
class OtpRoute:
    """A route discovered from the running graph, retaining feed-scoped identity."""

    feed_id: str
    gtfs_id: str
    scoped_id: str
    short_name: str | None
    long_name: str | None
    mode: str | None
    agency_id: str | None
    agency_name: str | None


def _as_str(value: Any) -> str | None:
    return value if isinstance(value, str) and value.strip() else None


def _as_int(value: Any) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _as_float(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _coordinate(value: Any, label: str, low: float, high: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} deve essere un numero")
    number = float(value)
    if not math.isfinite(number) or not (low <= number <= high):
        raise ValueError(f"{label} fuori range: {value!r}")
    return number


def _response_coordinate(value: Any, label: str, low: float, high: float) -> float:
    """Convert response-coordinate errors at the parser boundary."""
    try:
        return _coordinate(value, label, low, high)
    except ValueError as exc:
        raise OtpInvalidResponseError(f"{label}: coordinata non valida ({value!r})") from exc


def _required_time(value: Any, label: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise OtpInvalidResponseError(f"{label}: tempo mancante")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise OtpInvalidResponseError(f"{label}: tempo non interpretabile") from exc
    if parsed.tzinfo is None:
        raise OtpInvalidResponseError(f"{label}: tempo senza offset di fuso")
    return parsed


def _non_negative_seconds(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise OtpInvalidResponseError(f"{label}: durata non numerica")
    number = float(value)
    if not math.isfinite(number) or number < 0:
        raise OtpInvalidResponseError(f"{label}: durata non valida")
    return number


def _non_negative_integer_seconds(value: Any, label: str) -> int:
    number = _non_negative_seconds(value, label)
    if not number.is_integer():
        raise OtpInvalidResponseError(f"{label}: durata non intera")
    return int(number)


class OtpClient:
    """OTP 2.10 GraphQL client.

    ``mode="real"`` never falls back to a fixture. ``mode="demo"`` is a
    deterministic, network-free fixture path and always returns
    ``is_simulated=True``. The application profile describes persistence only;
    it does not select routing behavior.
    """

    def __init__(
        self,
        *,
        base_url: str = "http://localhost:8080",
        timeout_s: float = 5.0,
        mode: OtpMode = "real",
        timezone: str = "Europe/Rome",
        http_client: httpx.Client | None = None,
        fixture_path: str | Path | None = None,
    ) -> None:
        if mode not in ("real", "demo"):
            raise ValueError("mode deve essere 'real' o 'demo'")
        if timeout_s <= 0:
            raise ValueError("timeout_s deve essere positivo")
        try:
            self._timezone = ZoneInfo(timezone)
        except ZoneInfoNotFoundError as exc:
            raise ValueError(f"timezone sconosciuta: {timezone}") from exc

        self.base_url = base_url.rstrip("/")
        self.timeout_s = float(timeout_s)
        self.mode = mode
        self.timezone = timezone
        self.endpoint = f"{self.base_url}/otp/gtfs/v1"
        self._http_client = http_client
        self._fixture_path = Path(fixture_path) if fixture_path is not None else None

    def plan_itineraries(
        self,
        *,
        from_lat: float,
        from_lon: float,
        to_lat: float,
        to_lon: float,
        depart_at: datetime | None = None,
        arrive_by: datetime | None = None,
        first: int = 5,
        modes: Sequence[str] = DEFAULT_MODES,
        transit_only: bool = False,
        exclude_route_ids: Sequence[str] = (),
    ) -> ItineraryPlan:
        """Plan up to ``first`` itineraries and retain every candidate.

        Exclusions are feed-scoped route IDs (``feedId:routeId``). A route ID
        without a feed namespace is rejected instead of being guessed.
        """
        from_lat = _coordinate(from_lat, "from_lat", -90.0, 90.0)
        from_lon = _coordinate(from_lon, "from_lon", -180.0, 180.0)
        to_lat = _coordinate(to_lat, "to_lat", -90.0, 90.0)
        to_lon = _coordinate(to_lon, "to_lon", -180.0, 180.0)
        if depart_at is not None and arrive_by is not None:
            raise ValueError("specificare depart_at oppure arrive_by, non entrambi")
        if isinstance(modes, str) or not isinstance(modes, Sequence):
            raise TypeError("modes deve essere una sequenza di modalita")
        if isinstance(exclude_route_ids, str) or not isinstance(exclude_route_ids, Sequence):
            raise TypeError("exclude_route_ids deve essere una sequenza")
        if isinstance(first, bool) or not isinstance(first, int) or first < 1:
            raise ValueError("first deve essere un intero >= 1")

        route_ids = [str(item).strip() for item in exclude_route_ids]
        for route_id in route_ids:
            if not is_feed_scoped_id(route_id):
                raise ValueError(f"route id non feed-scoped: {route_id!r}; usare 'feedId:routeId'")

        modes_input = self._build_modes(list(modes), transit_only=transit_only)
        date_time = self._build_date_time(depart_at=depart_at, arrive_by=arrive_by)
        preferences = None
        if route_ids:
            preferences = {
                "transit": {
                    "filters": [{"exclude": [{"routes": route_ids}]}],
                }
            }

        if self.mode == "demo":
            return self._demo_plan()

        variables: dict[str, Any] = {
            "origin": {
                "location": {
                    "coordinate": {
                        "latitude": float(from_lat),
                        "longitude": float(from_lon),
                    }
                }
            },
            "destination": {
                "location": {
                    "coordinate": {
                        "latitude": float(to_lat),
                        "longitude": float(to_lon),
                    }
                }
            },
            "dateTime": date_time,
            "first": int(first),
            "modes": modes_input,
            "preferences": preferences,
        }
        payload = self._post(variables)
        return self._parse_plan(payload)

    def fetch_graph(self, query: str) -> dict[str, Any]:
        """Run a read-only GraphQL query against the live graph.

        This is used to discover feed-scoped identifiers and agencies. It is
        deliberately unavailable in demo mode: a recorded fixture cannot
        stand in for the current graph.
        """
        if not isinstance(query, str) or not query.strip():
            raise ValueError("query GraphQL vuota")
        if self.mode == "demo":
            raise OtpUnavailableError("scoperta del grafo non disponibile in modalita demo")
        response = self._execute(query, {})
        return response

    def discover_routes(
        self,
        *,
        short_name: str | None = None,
        agency_name: str | None = None,
    ) -> list[OtpRoute]:
        """Return routes from the live graph, filtered without assuming a feed ID.

        ``agency_name`` matches either the OTP agency *name* or its original
        GTFS ``agency_id`` (for example ANM / Azienda Napoletana Mobilità).
        """
        data = self.fetch_graph(ROUTES_QUERY)
        raw_routes = data.get("routes")
        if not isinstance(raw_routes, list):
            raise OtpInvalidResponseError("risposta OTP senza lista routes")

        short_filter = short_name.strip().casefold() if short_name else None
        agency_filter = agency_name.strip().casefold() if agency_name else None
        discovered: list[OtpRoute] = []
        for raw_route in raw_routes:
            if not isinstance(raw_route, dict):
                raise OtpInvalidResponseError("route OTP non valida")
            scoped_id = _as_str(raw_route.get("gtfsId"))
            if scoped_id is None:
                raise OtpInvalidResponseError("route OTP senza gtfsId")
            try:
                feed_id, gtfs_id = parse_otp_id(scoped_id)
            except ValueError as exc:
                raise OtpInvalidResponseError(
                    f"route OTP con gtfsId non feed-scoped: {scoped_id!r}"
                ) from exc

            short = _as_str(raw_route.get("shortName"))
            if short_filter is not None and (short or "").casefold() != short_filter:
                continue

            agency = raw_route.get("agency")
            agency = agency if isinstance(agency, dict) else {}
            agency_gtfs_id = _as_str(agency.get("gtfsId"))
            agency_gtfs_name = _as_str(agency.get("name"))
            agency_id: str | None = None
            if agency_gtfs_id is not None:
                try:
                    _, agency_id = parse_otp_id(agency_gtfs_id)
                except ValueError as exc:
                    raise OtpInvalidResponseError(
                        f"agency OTP con gtfsId non feed-scoped: {agency_gtfs_id!r}"
                    ) from exc
            if agency_filter is not None:
                haystack = " ".join(
                    part for part in (agency_id, agency_gtfs_name) if part
                ).casefold()
                if agency_filter not in haystack:
                    continue

            discovered.append(
                OtpRoute(
                    feed_id=feed_id,
                    gtfs_id=gtfs_id,
                    scoped_id=scoped_id,
                    short_name=short,
                    long_name=_as_str(raw_route.get("longName")),
                    mode=_as_str(raw_route.get("mode")),
                    agency_id=agency_id,
                    agency_name=agency_gtfs_name,
                )
            )
        return discovered

    def discover_feed_agencies(self) -> dict[str, set[str]]:
        """Map every OTP feed ID to the original GTFS agency IDs it exposes."""
        data = self.fetch_graph(AGENCIES_QUERY)
        raw_agencies = data.get("agencies")
        if not isinstance(raw_agencies, list):
            raise OtpInvalidResponseError("risposta OTP senza lista agencies")
        result: dict[str, set[str]] = {}
        for raw_agency in raw_agencies:
            if not isinstance(raw_agency, dict):
                raise OtpInvalidResponseError("agency OTP non valida")
            scoped_id = _as_str(raw_agency.get("gtfsId"))
            if scoped_id is None:
                raise OtpInvalidResponseError("agency OTP senza gtfsId")
            try:
                feed_id, agency_id = parse_otp_id(scoped_id)
            except ValueError as exc:
                raise OtpInvalidResponseError(
                    f"agency OTP con gtfsId non feed-scoped: {scoped_id!r}"
                ) from exc
            result.setdefault(feed_id, set()).add(agency_id)
        return result

    def _build_modes(self, modes: list[str], *, transit_only: bool) -> dict[str, Any]:
        if any(not isinstance(mode, str) for mode in modes):
            raise TypeError("modes deve contenere stringhe")
        normalized = [mode.strip().upper() for mode in modes if mode.strip()]
        if not normalized:
            raise ValueError("modes non puo' essere vuoto")
        unknown = [mode for mode in normalized if mode not in DIRECT_MODES | TRANSIT_MODES]
        if unknown:
            raise ValueError(f"modalita OTP non supportate: {unknown}")

        direct = [] if transit_only else [mode for mode in normalized if mode in DIRECT_MODES]
        transit = [{"mode": mode} for mode in normalized if mode in TRANSIT_MODES]
        if not transit:
            raise ValueError("serve almeno una modalita di trasporto pubblico")
        result: dict[str, Any] = {"direct": direct, "transit": {"transit": transit}}
        if transit_only:
            result["transitOnly"] = True
        return result

    def _build_date_time(
        self,
        *,
        depart_at: datetime | None,
        arrive_by: datetime | None,
    ) -> dict[str, str]:
        value = arrive_by or depart_at or datetime.now(self._timezone)
        if not isinstance(value, datetime):
            raise TypeError("data/ora non valida")
        if value.tzinfo is None:
            value = value.replace(tzinfo=self._timezone)
        key = "latestArrival" if arrive_by is not None else "earliestDeparture"
        return {key: value.isoformat()}

    def _post(self, variables: dict[str, Any]) -> dict[str, Any]:
        data = self._execute(PLAN_QUERY, variables)
        plan = data.get("planConnection")
        if not isinstance(plan, dict):
            raise OtpInvalidResponseError("risposta OTP senza planConnection")
        return plan

    def _execute(self, query: str, variables: dict[str, Any]) -> dict[str, Any]:
        payload = {"query": query, "variables": variables}
        try:
            if self._http_client is not None:
                response = self._http_client.post(
                    self.endpoint, json=payload, timeout=self.timeout_s
                )
            else:
                with httpx.Client(timeout=self.timeout_s) as client:
                    response = client.post(self.endpoint, json=payload)
        except httpx.TimeoutException as exc:
            raise OtpTimeoutError(f"timeout OTP dopo {self.timeout_s}s") from exc
        except httpx.RequestError as exc:
            raise OtpUnavailableError(f"OTP non raggiungibile: {type(exc).__name__}") from exc

        if response.status_code >= 400:
            raise OtpHttpError(response.status_code, response.text)

        try:
            body = response.json()
        except ValueError as exc:
            raise OtpInvalidResponseError("risposta OTP non JSON") from exc
        if not isinstance(body, dict):
            raise OtpInvalidResponseError("risposta OTP non e' un oggetto JSON")

        errors = body.get("errors")
        if errors:
            if not isinstance(errors, list):
                errors = [{"message": str(errors)}]
            raise OtpGraphQLError([item for item in errors if isinstance(item, dict)])

        data = body.get("data")
        if not isinstance(data, dict):
            raise OtpInvalidResponseError("risposta OTP senza campo data")
        return data

    def _parse_plan(self, plan: dict[str, Any]) -> ItineraryPlan:
        raw_errors = plan.get("routingErrors") or []
        if not isinstance(raw_errors, list):
            raise OtpInvalidResponseError("routingErrors non e' una lista")
        routing_errors = [item for item in raw_errors if isinstance(item, dict)]

        raw_edges = plan.get("edges")
        if not isinstance(raw_edges, list):
            raise OtpInvalidResponseError("planConnection.edges non e' una lista")

        itineraries: list[ItineraryResult] = []
        for edge in raw_edges:
            if not isinstance(edge, dict) or not isinstance(edge.get("node"), dict):
                raise OtpInvalidResponseError("itinerario OTP senza node")
            itineraries.append(self._parse_itinerary(edge["node"]))

        if not itineraries:
            raise OtpNoRouteError(routing_errors)

        return ItineraryPlan(
            itineraries=itineraries,
            routing_errors=routing_errors,
            is_simulated=False,
            source_id="otp",
            data_reference=self.endpoint,
        )

    def _parse_itinerary(self, node: dict[str, Any]) -> ItineraryResult:
        raw_legs = node.get("legs")
        if not isinstance(raw_legs, list) or not raw_legs:
            raise OtpInvalidResponseError("itinerario OTP senza legs")

        parsed_legs: list[tuple[dict[str, Any], datetime, datetime]] = []
        for raw_leg in raw_legs:
            if not isinstance(raw_leg, dict):
                raise OtpInvalidResponseError("leg OTP non valido")
            parsed_legs.append(self._parse_leg(raw_leg))

        previous_end: datetime | None = None
        for _, start_dt, end_dt in parsed_legs:
            if previous_end is not None:
                overlap = (start_dt - previous_end).total_seconds()
                if overlap < -TIME_TOLERANCE_S:
                    raise OtpInvalidResponseError("leg OTP sovrapposti o fuori ordine")
            previous_end = end_dt

        first_start = parsed_legs[0][1]
        last_end = parsed_legs[-1][2]
        raw_start = node.get("start")
        raw_end = node.get("end")
        if (raw_start is None) != (raw_end is None):
            raise OtpInvalidResponseError("itinerario OTP con estremi incompleti")
        if raw_start is not None:
            start_dt = _required_time(raw_start, "itinerary.start")
            end_dt = _required_time(raw_end, "itinerary.end")
            if end_dt < start_dt:
                raise OtpInvalidResponseError("itinerario OTP con end precedente a start")
            if abs((first_start - start_dt).total_seconds()) > TIME_TOLERANCE_S:
                raise OtpInvalidResponseError("itinerario OTP incoerente con il primo leg")
            if abs((last_end - end_dt).total_seconds()) > TIME_TOLERANCE_S:
                raise OtpInvalidResponseError("itinerario OTP incoerente con l'ultimo leg")
            start = raw_start
            end = raw_end
        else:
            start_dt = first_start
            end_dt = last_end
            start = start_dt.isoformat()
            end = end_dt.isoformat()

        duration = int((end_dt - start_dt).total_seconds())
        if duration < 0:
            raise OtpInvalidResponseError("itinerario OTP con durata negativa")
        raw_duration = node.get("duration")
        if raw_duration is not None:
            declared = _non_negative_integer_seconds(raw_duration, "itinerary.duration")
            if abs(declared - duration) > TIME_TOLERANCE_S:
                raise OtpInvalidResponseError("itinerario OTP con durata incoerente con start/end")

        return ItineraryResult(
            start=start,
            end=end,
            duration_s=duration,
            walk_time_s=_as_int(node.get("walkTime")),
            walk_distance_m=_as_float(node.get("walkDistance")),
            transfers=_as_int(node.get("numberOfTransfers")),
            generalized_cost=_as_int(node.get("generalizedCost")),
            legs=[item[0] for item in parsed_legs],
            raw=node,
        )

    def _estimated_time(self, leg_time: dict[str, Any], label: str) -> datetime | None:
        estimated = leg_time.get("estimated")
        if estimated is None:
            return None
        if not isinstance(estimated, dict):
            raise OtpInvalidResponseError(f"{label}.estimated non valido")
        raw_time = estimated.get("time")
        if raw_time is None:
            return None
        return _required_time(raw_time, f"{label}.estimated.time")

    def _parse_leg(self, leg: dict[str, Any]) -> tuple[dict[str, Any], datetime, datetime]:
        mode = _as_str(leg.get("mode"))
        if mode is None:
            raise OtpInvalidResponseError("leg OTP senza mode")

        start = leg.get("start")
        end = leg.get("end")
        if not isinstance(start, dict) or not isinstance(end, dict):
            raise OtpInvalidResponseError("leg OTP senza start/end")
        start_scheduled = _required_time(start.get("scheduledTime"), "leg.start.scheduledTime")
        end_scheduled = _required_time(end.get("scheduledTime"), "leg.end.scheduledTime")
        start_estimated = self._estimated_time(start, "leg.start")
        end_estimated = self._estimated_time(end, "leg.end")
        effective_start = start_estimated or start_scheduled
        effective_end = end_estimated or end_scheduled
        if effective_end < effective_start:
            raise OtpInvalidResponseError("leg OTP con end precedente a start")

        computed_duration = (effective_end - effective_start).total_seconds()
        raw_duration = leg.get("duration")
        if raw_duration is not None:
            declared_duration = _non_negative_seconds(raw_duration, "leg.duration")
            if abs(declared_duration - computed_duration) > TIME_TOLERANCE_S:
                raise OtpInvalidResponseError("leg OTP con durata incoerente con i tempi")
        duration = computed_duration

        from_place = leg.get("from")
        to_place = leg.get("to")
        if not isinstance(from_place, dict) or not isinstance(to_place, dict):
            raise OtpInvalidResponseError("leg OTP senza from/to")
        from_lat = _response_coordinate(from_place.get("lat"), "leg.from.lat", -90.0, 90.0)
        from_lon = _response_coordinate(from_place.get("lon"), "leg.from.lon", -180.0, 180.0)
        to_lat = _response_coordinate(to_place.get("lat"), "leg.to.lat", -90.0, 90.0)
        to_lon = _response_coordinate(to_place.get("lon"), "leg.to.lon", -180.0, 180.0)

        from_stop = from_place.get("stop") if isinstance(from_place.get("stop"), dict) else {}
        to_stop = to_place.get("stop") if isinstance(to_place.get("stop"), dict) else {}
        from_stop_id = _as_str(from_stop.get("gtfsId"))
        to_stop_id = _as_str(to_stop.get("gtfsId"))

        route = leg.get("route") if isinstance(leg.get("route"), dict) else {}
        trip = leg.get("trip") if isinstance(leg.get("trip"), dict) else {}
        route_short_name = _as_str(route.get("shortName"))
        route_id = _as_str(route.get("gtfsId"))
        trip_id = _as_str(trip.get("gtfsId"))
        agency = route.get("agency") if isinstance(route.get("agency"), dict) else {}
        agency_gtfs_id = _as_str(agency.get("gtfsId"))
        agency_name = _as_str(agency.get("name"))
        agency_id: str | None = None
        if agency_gtfs_id is not None:
            try:
                _, agency_id = parse_otp_id(agency_gtfs_id)
            except ValueError as exc:
                raise OtpInvalidResponseError(
                    f"leg OTP con route.agency.gtfsId non feed-scoped: {agency_gtfs_id!r}"
                ) from exc

        transit_flag = leg.get("transitLeg")
        if transit_flag is not None and not isinstance(transit_flag, bool):
            raise OtpInvalidResponseError("leg OTP con transitLeg non booleano")
        is_transit = bool(transit_flag) or mode in TRANSIT_MODES
        if is_transit:
            missing = [
                name
                for name, value in (
                    ("route.gtfsId", route_id),
                    ("trip.gtfsId", trip_id),
                    ("from.stop.gtfsId", from_stop_id),
                    ("to.stop.gtfsId", to_stop_id),
                )
                if value is None
            ]
            if missing:
                raise OtpInvalidResponseError(
                    f"leg transit OTP senza identificativi: {', '.join(missing)}"
                )

        geometry = leg.get("legGeometry") if isinstance(leg.get("legGeometry"), dict) else {}
        return (
            {
                "mode": mode,
                "transit_leg": is_transit,
                "duration_s": duration,
                "start_scheduled": start_scheduled.isoformat(),
                "start_estimated": (
                    start_estimated.isoformat() if start_estimated is not None else None
                ),
                "start_delay_s": (
                    start.get("estimated", {}).get("delay")
                    if isinstance(start.get("estimated"), dict)
                    else None
                ),
                "end_scheduled": end_scheduled.isoformat(),
                "end_estimated": (end_estimated.isoformat() if end_estimated is not None else None),
                "end_delay_s": (
                    end.get("estimated", {}).get("delay")
                    if isinstance(end.get("estimated"), dict)
                    else None
                ),
                "route": route_short_name or route_id,
                "route_id": route_id,
                "route_short_name": route_short_name,
                "route_long_name": _as_str(route.get("longName")),
                "route_mode": _as_str(route.get("mode")),
                "agency_id": agency_id,
                "agency_gtfs_id": agency_gtfs_id,
                "agency_name": agency_name,
                "operator": agency_name or agency_id,
                "trip_id": trip_id,
                "from_stop_id": from_stop_id,
                "to_stop_id": to_stop_id,
                "from_name": _as_str(from_place.get("name")),
                "to_name": _as_str(to_place.get("name")),
                "from_lat": from_lat,
                "from_lon": from_lon,
                "to_lat": to_lat,
                "to_lon": to_lon,
                "geometry": _as_str(geometry.get("points")),
                "geometry_length": _as_int(geometry.get("length")),
            },
            effective_start,
            effective_end,
        )

    def _demo_plan(self) -> ItineraryPlan:
        path = self._fixture_path
        if path is None:
            repo_root = Path(__file__).resolve().parents[5]
            path = repo_root / "shared" / "mocks" / "otp_fixture.json"
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise OtpInvalidResponseError(f"fixture demo non leggibile: {path}") from exc
        raw_itineraries = (raw.get("plan") or {}).get("itineraries") or []
        if not isinstance(raw_itineraries, list) or not raw_itineraries:
            raise OtpInvalidResponseError("fixture demo senza itinerari")

        itineraries: list[ItineraryResult] = []
        for item in raw_itineraries:
            if not isinstance(item, dict):
                continue
            raw_legs = item.get("legs") if isinstance(item.get("legs"), list) else []
            legs: list[dict[str, Any]] = []
            for raw_leg in raw_legs:
                if not isinstance(raw_leg, dict):
                    continue
                from_place = raw_leg.get("from") if isinstance(raw_leg.get("from"), dict) else {}
                to_place = raw_leg.get("to") if isinstance(raw_leg.get("to"), dict) else {}
                route_label = _as_str(raw_leg.get("route"))
                legs.append(
                    {
                        "mode": _as_str(raw_leg.get("mode")) or "UNKNOWN",
                        "transit_leg": True,
                        "duration_s": _as_float(raw_leg.get("duration")),
                        "start_scheduled": None,
                        "start_estimated": None,
                        "start_delay_s": None,
                        "end_scheduled": None,
                        "end_estimated": None,
                        "end_delay_s": None,
                        "route": route_label,
                        "route_id": None,
                        "route_short_name": route_label,
                        "route_long_name": None,
                        "route_mode": _as_str(raw_leg.get("mode")),
                        "agency_id": None,
                        "agency_gtfs_id": None,
                        "agency_name": None,
                        "operator": None,
                        "trip_id": None,
                        "from_stop_id": _as_str(from_place.get("stopId")),
                        "to_stop_id": _as_str(to_place.get("stopId")),
                        "from_name": _as_str(from_place.get("name")),
                        "to_name": _as_str(to_place.get("name")),
                        "from_lat": _as_float(from_place.get("lat")),
                        "from_lon": _as_float(from_place.get("lon")),
                        "to_lat": _as_float(to_place.get("lat")),
                        "to_lon": _as_float(to_place.get("lon")),
                        "geometry": None,
                        "geometry_length": None,
                    }
                )
            itineraries.append(
                ItineraryResult(
                    start=None,
                    end=None,
                    duration_s=_as_int(item.get("duration")),
                    walk_time_s=None,
                    walk_distance_m=_as_float(item.get("walkDistance")),
                    transfers=None,
                    generalized_cost=None,
                    legs=legs,
                    raw=item,
                )
            )
        if not itineraries:
            raise OtpInvalidResponseError("fixture demo senza itinerari validi")
        return ItineraryPlan(
            itineraries=itineraries,
            routing_errors=[],
            is_simulated=True,
            source_id="otp_fixture",
            data_reference=f"fixture:{path}",
            fallback_reason="demo_mode_fixture",
        )
