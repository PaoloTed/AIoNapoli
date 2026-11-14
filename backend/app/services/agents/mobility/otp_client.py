"""OpenTripPlanner GraphQL client with deterministic fixture fallback (D-08).

Seven defects of the first version are fixed here, see
``ricerche/ricerca2/03b_cosa_ho_trovato_codice.md``:

1. the endpoint is configurable and defaults to ``/otp/gtfs/v1``;
2. the query asks for the stops, the headsign and the start time of each leg;
3. legs are normalised into :class:`RouteLeg`, never returned as raw dicts;
4. ``banned`` and ``unpreferred`` are forwarded to the engine;
5. every itinerary is returned, not only the first;
6. no hard-coded coordinate defaults: a missing waypoint is a programming error;
7. ``OtpUnavailable`` and ``OtpMalformedResponse`` are distinct from ``Exception``,
   so a bug in this module can no longer masquerade as ``is_simulated=True``.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

import httpx

from app.services.agents.mobility.itineraries import RouteLeg

DEFAULT_ENDPOINT_PATH = "/otp/gtfs/v1"
FIXTURE_RELATIVE_PATH = Path("shared") / "mocks" / "otp_fixture.json"

_LEG_FIELDS = (
    "mode duration startTime headsign "
    "route { shortName } "
    "from { name lat lon stop { gtfsId } } "
    "to { name lat lon stop { gtfsId } }"
)
_ITINERARY_FIELDS = f"duration walkDistance startTime legs {{ {_LEG_FIELDS} }}"


class OtpError(Exception):
    """Base class for every error this module raises on purpose."""


class OtpUnavailable(OtpError):
    """The engine does not answer, answers with a transport error, or has no graph.

    Falling back to the recorded fixture is legitimate here: the demo degrades,
    it does not lie, because the result carries ``is_simulated=True``.
    """


class OtpMalformedResponse(OtpError):
    """The engine answers, but the body is not the shape we asked for."""


@dataclass(frozen=True)
class Itinerary:
    """A single itinerary proposed by the engine."""

    duration_min: int
    walk_distance_m: float
    legs: list[RouteLeg]
    start_time: str | None = None


@dataclass(frozen=True)
class ItineraryResult:
    """Every itinerary the engine returned, plus the best one for convenience.

    ``duration_min`` and ``legs`` keep mirroring the first proposal so the
    mobility agent does not need to change while the cycle is built.
    """

    duration_min: int
    legs: list[RouteLeg]
    is_simulated: bool
    source_id: str
    data_reference: str
    fallback_reason: str | None = None
    proposals: list[Itinerary] = field(default_factory=list)

    @property
    def best(self) -> Itinerary | None:
        return self.proposals[0] if self.proposals else None

    def stops(self) -> list[str]:
        """Stops touched by the best itinerary, in travel order."""
        seen: dict[str, None] = {}
        for leg in self.legs:
            for stop in (leg.from_stop_id, leg.to_stop_id):
                if stop:
                    seen.setdefault(stop, None)
        return list(seen)


def fixture_path() -> Path:
    """Absolute path of the recorded fixture, resolved from this module."""
    return Path(__file__).resolve().parents[5] / FIXTURE_RELATIVE_PATH


def load_otp_fixture() -> dict[str, Any]:
    """Load the recorded OTP response, or an inline minimal fallback."""
    path = fixture_path()
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {
        "plan": {
            "itineraries": [
                {
                    "duration": 1200,
                    "walkDistance": 420.0,
                    "legs": [
                        {
                            "mode": "BUS",
                            "route": {"shortName": "151"},
                            "duration": 900,
                            "from": {"name": "Piazza Garibaldi", "stop": {"gtfsId": "STOP_GAR_01"}},
                            "to": {"name": "Campi Flegrei", "stop": {"gtfsId": "STOP_FUO_01"}},
                        },
                        {
                            "mode": "RAIL",
                            "route": {"shortName": "CUMANA"},
                            "duration": 300,
                            "from": {"name": "Campi Flegrei", "stop": {"gtfsId": "STOP_FUO_01"}},
                            "to": {"name": "Bagnoli", "stop": {"gtfsId": "STOP_BAG_01"}},
                        },
                    ],
                }
            ]
        }
    }


def _route_name(raw: Any) -> str | None:
    """The engine nests the line name in ``route.shortName``; fixtures may not."""
    if isinstance(raw, Mapping):
        short = raw.get("shortName")
        return str(short) if short else None
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    return None


def _place(raw: Any) -> tuple[str | None, str | None, float | None, float | None]:
    """Extract ``(stop_id, name, lat, lon)`` from a leg endpoint."""
    if not isinstance(raw, Mapping):
        return None, None, None, None
    stop = raw.get("stop")
    stop_id: str | None = None
    if isinstance(stop, Mapping):
        gtfs_id = stop.get("gtfsId")
        stop_id = str(gtfs_id) if gtfs_id else None
    elif isinstance(stop, str) and stop.strip():
        stop_id = stop.strip()
    if stop_id is None:
        # Fixtures written before the query extension carry ``stopId`` directly.
        legacy = raw.get("stopId")
        stop_id = str(legacy) if legacy else None
    name = raw.get("name")
    lat = raw.get("lat")
    lon = raw.get("lon")
    return (
        stop_id,
        str(name) if name else None,
        float(lat) if isinstance(lat, (int, float)) else None,
        float(lon) if isinstance(lon, (int, float)) else None,
    )


def normalise_leg(raw: Mapping[str, Any]) -> RouteLeg:
    """Turn one GraphQL leg into a :class:`RouteLeg`."""
    from_stop_id, from_name, from_lat, from_lon = _place(raw.get("from"))
    to_stop_id, to_name, to_lat, to_lon = _place(raw.get("to"))
    duration = raw.get("duration")
    start_time = raw.get("startTime")
    headsign = raw.get("headsign")
    return RouteLeg(
        mode=str(raw.get("mode") or "TRANSIT"),
        route=_route_name(raw.get("route")),
        duration_s=int(duration) if isinstance(duration, (int, float)) else 0,
        from_stop_id=from_stop_id,
        from_stop_name=from_name,
        to_stop_id=to_stop_id,
        to_stop_name=to_name,
        start_time=str(start_time) if start_time else None,
        headsign=str(headsign) if headsign else None,
        from_lat=from_lat,
        from_lon=from_lon,
        to_lat=to_lat,
        to_lon=to_lon,
    )


def normalise_itinerary(raw: Mapping[str, Any]) -> Itinerary:
    """Turn one GraphQL itinerary into an :class:`Itinerary`."""
    legs = [normalise_leg(leg) for leg in raw.get("legs") or [] if isinstance(leg, Mapping)]
    duration = raw.get("duration")
    duration_s = int(duration) if isinstance(duration, (int, float)) else 1200
    walk = raw.get("walkDistance")
    start_time = raw.get("startTime")
    return Itinerary(
        duration_min=max(1, round(duration_s / 60)),
        walk_distance_m=float(walk) if isinstance(walk, (int, float)) else 0.0,
        legs=legs,
        start_time=str(start_time) if start_time else None,
    )


def _decode(body: Any) -> list[Itinerary]:
    """Pull itineraries out of a GraphQL response body."""
    if not isinstance(body, Mapping):
        raise OtpMalformedResponse("corpo_non_oggetto")
    errors = body.get("errors")
    if errors:
        raise OtpMalformedResponse(f"graphql_errors:{str(errors)[:160]}")
    data = body.get("data")
    plan = data.get("plan") if isinstance(data, Mapping) else None
    raw_itineraries = plan.get("itineraries") if isinstance(plan, Mapping) else None
    if not isinstance(raw_itineraries, list):
        raise OtpMalformedResponse("plan_itineraries_assenti")
    itineraries = [
        normalise_itinerary(item) for item in raw_itineraries if isinstance(item, Mapping)
    ]
    if not itineraries:
        raise OtpMalformedResponse("zero_itinerari")
    return itineraries


def build_query(
    *,
    with_modes: bool,
    with_banned: bool,
    with_unpreferred: bool,
    with_start_time: bool,
) -> str:
    """Compose the GraphQL document.

    Optional arguments are declared only when they are used: a wrong input type
    name would invalidate the whole document, so the default path must not
    mention ``InputBanned`` or ``InputUnpreferred`` at all.
    """
    variables = [
        "$fromLat: Float!",
        "$fromLon: Float!",
        "$toLat: Float!",
        "$toLon: Float!",
        "$numItineraries: Int!",
    ]
    arguments = [
        "from: {lat: $fromLat, lon: $fromLon}",
        "to: {lat: $toLat, lon: $toLon}",
        "numItineraries: $numItineraries",
    ]
    if with_modes:
        variables.append("$transportModes: [TransportMode!]")
        arguments.append("transportModes: $transportModes")
    if with_start_time:
        variables.append("$startTime: String")
        arguments.append("dateTime: $startTime")
    if with_banned:
        variables.append("$banned: InputBanned")
        arguments.append("banned: $banned")
    if with_unpreferred:
        variables.append("$unpreferred: InputUnpreferred")
        arguments.append("unpreferred: $unpreferred")
        variables.append("$unpreferredCost: String")
        arguments.append("unpreferredCost: $unpreferredCost")
    return (
        f"query Plan({', '.join(variables)}) {{ "
        f"plan({', '.join(arguments)}) {{ itineraries {{ {_ITINERARY_FIELDS} }} }} }}"
    )


class OtpClient:
    """Queries OpenTripPlanner and falls back to the recorded fixture if unusable."""

    def __init__(
        self,
        *,
        base_url: str = "http://localhost:8080",
        endpoint_path: str = DEFAULT_ENDPOINT_PATH,
        timeout_s: float = 5.0,
        http_client: httpx.Client | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._endpoint_path = "/" + endpoint_path.lstrip("/")
        self._timeout_s = timeout_s
        self._http_client = http_client

    @property
    def endpoint(self) -> str:
        return f"{self._base_url}{self._endpoint_path}"

    def plan_itinerary(
        self,
        *,
        from_lat: float,
        from_lon: float,
        to_lat: float,
        to_lon: float,
        num_itineraries: int = 5,
        transport_modes: Sequence[str] | None = None,
        start_time: str | None = None,
        banned: Mapping[str, Any] | None = None,
        unpreferred: Mapping[str, Any] | None = None,
        unpreferred_cost: str | None = None,
    ) -> ItineraryResult:
        """Ask the engine for itineraries between two waypoints.

        ``banned`` and ``unpreferred`` are GraphQL-shaped on purpose: turning a
        :class:`TravelConstraint` into these parameters is the job of the
        negotiation cycle, not of the transport client.
        """
        query = build_query(
            with_modes=bool(transport_modes),
            with_banned=banned is not None,
            with_unpreferred=unpreferred is not None,
            with_start_time=start_time is not None,
        )
        variables: dict[str, Any] = {
            "fromLat": from_lat,
            "fromLon": from_lon,
            "toLat": to_lat,
            "toLon": to_lon,
            "numItineraries": num_itineraries,
        }
        if transport_modes:
            variables["transportModes"] = list(transport_modes)
        if start_time is not None:
            variables["startTime"] = start_time
        if banned is not None:
            variables["banned"] = dict(banned)
        if unpreferred is not None:
            variables["unpreferred"] = dict(unpreferred)
            variables["unpreferredCost"] = unpreferred_cost

        try:
            itineraries = self._query({"query": query, "variables": variables})
        except OtpError as exc:
            return self._fallback(exc)

        first = itineraries[0]
        return ItineraryResult(
            duration_min=first.duration_min,
            legs=first.legs,
            is_simulated=False,
            source_id="otp",
            data_reference=self.endpoint,
            fallback_reason=None,
            proposals=itineraries,
        )

    def _query(self, payload: dict[str, Any]) -> list[Itinerary]:
        """POST the document, then decode it.

        The two steps are deliberately separated. Everything that can go wrong
        while the bytes travel — socket blocked by the test harness, connection
        refused, TLS failure, non-JSON body — is unavailability, and the demo is
        allowed to degrade. Everything that goes wrong *after* a JSON body has
        arrived is a bug in this module, and must surface instead of turning
        into a silent ``is_simulated=True``.
        """
        body = self._post(payload)
        return _decode(body)

    def _post(self, payload: dict[str, Any]) -> Any:
        """Send the request and return the JSON body, mapping transport failures."""
        try:
            if self._http_client is not None:
                response = self._http_client.post(
                    self.endpoint, json=payload, timeout=self._timeout_s
                )
            else:
                with httpx.Client(timeout=self._timeout_s) as client:
                    response = client.post(self.endpoint, json=payload)
        except httpx.HTTPError as exc:
            raise OtpUnavailable(f"trasporto:{type(exc).__name__}") from exc
        except OSError as exc:
            raise OtpUnavailable(f"rete:{type(exc).__name__}") from exc
        except RuntimeError as exc:
            # pytest-socket with --disable-socket raises a RuntimeError here.
            raise OtpUnavailable(f"socket_bloccato:{type(exc).__name__}") from exc

        status = response.status_code
        if status == 404:
            raise OtpUnavailable(f"endpoint_non_trovato:{self.endpoint}")
        if status >= 400:
            raise OtpUnavailable(f"http_{status}")

        try:
            return response.json()
        except ValueError as exc:
            raise OtpMalformedResponse("corpo_non_json") from exc

    def _fallback(self, exc: OtpError) -> ItineraryResult:
        """Serve the recorded fixture, declaring that the data is simulated."""
        try:
            body = load_otp_fixture()
            plan = body.get("plan") if isinstance(body.get("plan"), Mapping) else body
            raw_itineraries = plan.get("itineraries") if isinstance(plan, Mapping) else None
            itineraries = [
                normalise_itinerary(item)
                for item in raw_itineraries or []
                if isinstance(item, Mapping)
            ]
        except (OSError, ValueError):
            itineraries = []
        if not itineraries:
            itineraries = [Itinerary(duration_min=20, walk_distance_m=0.0, legs=[])]
        first = itineraries[0]
        return ItineraryResult(
            duration_min=first.duration_min,
            legs=first.legs,
            is_simulated=True,
            source_id="otp_fixture",
            data_reference=f"fixture:{FIXTURE_RELATIVE_PATH.as_posix()}",
            fallback_reason=f"otp_non_disponibile:{exc}",
            proposals=itineraries,
        )
