"""Local place resolution over GTFS/OSM catalogues, with optional Nominatim."""

from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Any

import httpx
from shared.schemas.journeys import ClarificationCandidate, Coordinate, ResolvedPlace

from app.domain.models.config import AppConfig

_SCHEMA_RE = re.compile(r"^[a-z_][a-z0-9_]*$")
_ALIASES = {
    "mann": "Museo archeologico nazionale di Napoli",
    "museo archeologico": "Museo archeologico nazionale di Napoli",
    "museo archeologico nazionale": "Museo archeologico nazionale di Napoli",
    "citta della scienza": "Citta della Scienza",
    "città della scienza": "Citta della Scienza",
    "metrò chiaiano": "METRO CHIAIANO",
    "metro chiaiano": "METRO CHIAIANO",
    "stazione chiaiano": "METRO CHIAIANO",
    "piazza garibaldi": "Piazza Garibaldi",
    "garibaldi": "Piazza Garibaldi",
    "stazione centrale": "Napoli Centrale",
    "centro direzionale": "Centro Direzionale",
    "aeroporto": "Aeroporto di Napoli",
    "capodichino": "Aeroporto di Napoli",
    "porto": "Molo Beverello",
    "molo beverello": "Molo Beverello",
    "universita": "Universita degli Studi di Napoli Federico II",
}
_TRANSLATE_FROM = "àáâäãåèéêëìíîïòóôöõùúûüçñ"
_TRANSLATE_TO = "aaaaaaeeeeiiiiooooouuuucn"


def _distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    import math

    radius = 6371008.8
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = (
        math.sin(dphi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    )
    return 2 * radius * math.asin(min(1.0, math.sqrt(a)))


def normalize(value: str) -> str:
    text = unicodedata.normalize("NFKD", value.casefold())
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


@dataclass
class PlaceCandidate:
    candidate_id: str
    label: str
    lat: float
    lon: float
    source: str
    approximate: bool = False
    detail: str | None = None
    score: float = 0.0

    def to_schema(self) -> ClarificationCandidate:
        return ClarificationCandidate(
            candidate_id=self.candidate_id,
            label=self.label,
            lat=self.lat,
            lon=self.lon,
            source=self.source,
            approximate=self.approximate,
            detail=self.detail,
        )


@dataclass
class PlaceResolution:
    status: str  # resolved | ambiguous | not_found | needs_client_location
    place: ResolvedPlace | None = None
    candidates: list[PlaceCandidate] = field(default_factory=list)
    message: str | None = None


class PlaceResolver:
    """Deterministic local resolver with stable candidate identifiers."""

    def __init__(
        self,
        conn: Any,
        config: AppConfig,
        *,
        gtfs_schemas: dict[str, str] | None = None,
        osm_schema: str | None = None,
        http_client: httpx.Client | None = None,
    ) -> None:
        self._conn = conn
        self._config = config
        self._gtfs_schemas = gtfs_schemas or config.gtfs_datasets
        self._osm_schema = osm_schema or config.osm_schema
        if not _SCHEMA_RE.fullmatch(self._osm_schema):
            raise ValueError(f"schema OSM non valido: {self._osm_schema!r}")
        for key, schema in self._gtfs_schemas.items():
            if not _SCHEMA_RE.fullmatch(schema):
                raise ValueError(f"schema GTFS non valido: {schema!r}")
        self._http_client = http_client

    def _row(self, cur: Any, row: Any) -> dict[str, Any]:
        if isinstance(row, dict):
            return dict(row)
        if hasattr(row, "keys"):
            return {key: row[key] for key in row.keys()}
        cols = [desc[0] for desc in cur.description]
        return dict(zip(cols, row))

    def _fetchall(self, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        cur = self._conn.cursor()
        cur.execute(sql, params)
        return [self._row(cur, row) for row in cur.fetchall()]

    @staticmethod
    def _translated(column: str) -> str:
        return f"translate(lower(coalesce({column},'')), '{_TRANSLATE_FROM}', '{_TRANSLATE_TO}')"

    def _patterns(self, query: str) -> list[str]:
        normalized = normalize(query)
        patterns = [f"%{normalized}%"] if normalized else []
        tokens = [token for token in normalized.split() if len(token) >= 4]
        if not patterns or normalized not in {"", "via", "piazza"}:
            for token in sorted(tokens, key=len, reverse=True)[:2]:
                candidate = f"%{token}%"
                if candidate not in patterns:
                    patterns.append(candidate)
        return patterns or [f"%{normalized}%"]

    def _stop_rows(self, patterns: list[str]) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for dataset, schema in self._gtfs_schemas.items():
            for pattern in patterns:
                rows.extend(
                    self._fetchall(
                        f"""
                        SELECT 'gtfs:' || r.dataset_key || ':stop:' || r.entity_id
                                   AS candidate_id,
                               r.display_name AS label,
                               r.dataset_key,
                               r.entity_id,
                               ST_Y(s.stop_loc::geometry) AS lat,
                               ST_X(s.stop_loc::geometry) AS lon
                        FROM public.reference_entities r
                        JOIN "{schema}".stops s ON s.stop_id = r.entity_id
                        WHERE r.domain = 'gtfs' AND r.dataset_key = %s
                          AND r.entity_type = 'stop' AND r.is_current
                          AND {self._translated("r.display_name")} LIKE %s
                        ORDER BY r.entity_id
                        LIMIT 20
                        """,
                        (dataset, pattern),
                    )
                )
        return self._dedupe(rows, "candidate_id")

    def _poi_rows(self, patterns: list[str]) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for pattern in patterns:
            rows.extend(
                self._fetchall(
                    f"""
                    SELECT 'osm:poi:' || osm_key AS candidate_id,
                           coalesce(name, name_it, osm_key) AS label,
                           category, category_value,
                           ST_Y(label_point::geometry) AS lat,
                           ST_X(label_point::geometry) AS lon
                    FROM "{self._osm_schema}".pois
                    WHERE is_current
                      AND ({self._translated("name")} LIKE %s
                           OR {self._translated("name_it")} LIKE %s)
                    ORDER BY
                      CASE WHEN ST_Y(label_point::geometry) BETWEEN 40.70 AND 41.00
                                AND ST_X(label_point::geometry) BETWEEN 13.90 AND 14.50
                           THEN 0 ELSE 1 END,
                      length(coalesce(name, name_it, '')), osm_key
                    LIMIT 60
                    """,
                    (pattern, pattern),
                )
            )
        return self._dedupe(rows, "candidate_id")

    def _way_rows(self, patterns: list[str]) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for pattern in patterns:
            rows.extend(
                self._fetchall(
                    f"""
                    SELECT osm_key, name, name_it, ref, highway,
                           ST_Y(ST_LineInterpolatePoint(geom, 0.5)) AS lat,
                           ST_X(ST_LineInterpolatePoint(geom, 0.5)) AS lon
                    FROM "{self._osm_schema}".osm_ways
                    WHERE is_current
                      AND ({self._translated("name")} LIKE %s
                           OR {self._translated("name_it")} LIKE %s
                           OR {self._translated("ref")} LIKE %s)
                    ORDER BY
                      CASE WHEN ST_Y(ST_LineInterpolatePoint(geom, 0.5))
                                      BETWEEN 40.70 AND 41.00
                                AND ST_X(ST_LineInterpolatePoint(geom, 0.5))
                                      BETWEEN 13.90 AND 14.50
                           THEN 0 ELSE 1 END,
                      length(coalesce(name, name_it, '')), osm_key
                    LIMIT 100
                    """,
                    (pattern, pattern, pattern),
                )
            )
        return self._dedupe(rows, "osm_key")

    @staticmethod
    def _dedupe(rows: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
        result: dict[str, dict[str, Any]] = {}
        for row in rows:
            result[str(row[key])] = row
        return list(result.values())

    @staticmethod
    def _local_bonus(lat: float, lon: float) -> float:
        # The catalogue is centred on Naples but contains a wider Campania
        # extract. This bonus only breaks textual ties; it never invents a
        # location when no textual match exists.
        return 0.08 if 40.70 <= lat <= 41.00 and 13.90 <= lon <= 14.50 else 0.0

    def _score(self, label: str, query: str, source: str, *, lat: float, lon: float) -> float:
        label_norm = normalize(label)
        query_norm = normalize(query)
        if not label_norm or not query_norm:
            return 0.0
        if label_norm == query_norm:
            score = 1.0
        elif label_norm.startswith(query_norm):
            score = 0.92
        elif query_norm in label_norm:
            score = 0.84
        else:
            label_tokens = set(label_norm.split())
            query_tokens = set(query_norm.split())
            overlap = len(label_tokens & query_tokens) / max(1, len(query_tokens))
            similarity = SequenceMatcher(None, label_norm, query_norm).ratio()
            score = 0.55 * overlap + 0.35 * similarity
        # Stable, documented preference for an exact transit stop over a
        # polygon/street label when the textual match is equal.
        score += {"stop": 0.03, "poi": 0.02, "way": 0.01, "client": 0.0}.get(source, 0.0)
        return score + self._local_bonus(lat, lon)

    def _prepare_query(self, text: str) -> tuple[str, str | None]:
        normalized = normalize(text)
        preferred: str | None = None
        if normalized.startswith(("via ", "viale ", "corso ", "strada ", "piazza ")):
            preferred = "way" if not normalized.startswith("piazza ") else "poi"
        if any(token in normalized for token in ("metro", "stazione", "fermata")):
            preferred = "stop"
        if any(
            token in normalized
            for token in ("museo", "mann", "mostra", "teatro", "aeroporto", "porto", "molo")
        ):
            preferred = "poi"
        alias = _ALIASES.get(normalized)
        return alias or text, preferred

    def _candidate_from_rows(
        self,
        rows: list[dict[str, Any]],
        source: str,
        query: str,
    ) -> list[PlaceCandidate]:
        result = []
        for row in rows:
            label = str(row.get("label") or row.get("name") or row.get("name_it") or "")
            lat, lon = row.get("lat"), row.get("lon")
            if lat is None or lon is None or not label:
                continue
            result.append(
                PlaceCandidate(
                    candidate_id=str(row["candidate_id"]) if "candidate_id" in row else "",
                    label=label,
                    lat=float(lat),
                    lon=float(lon),
                    source=source,
                    approximate=source == "way",
                    detail=(
                        f"{row.get('highway')} {row.get('ref') or ''}".strip()
                        if source == "way"
                        else (row.get("category") or None)
                    ),
                    score=self._score(label, query, source, lat=float(lat), lon=float(lon)),
                )
            )
        return result

    def _group_ways(self, rows: list[dict[str, Any]], query: str) -> list[PlaceCandidate]:
        groups: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            label = str(row.get("name") or row.get("name_it") or "")
            if not label:
                continue
            groups.setdefault(normalize(label), []).append(row)
        result: list[PlaceCandidate] = []
        for name, segments in groups.items():
            # The same name can exist in different municipalities. Group only
            # spatially connected segments: one street is one place, disjoint
            # same-name streets remain separate candidates.
            clusters: list[list[dict[str, Any]]] = []
            for segment in segments:
                lat = float(segment["lat"])
                lon = float(segment["lon"])
                assigned = False
                for cluster in clusters:
                    centre_lat = sum(float(item["lat"]) for item in cluster) / len(cluster)
                    centre_lon = sum(float(item["lon"]) for item in cluster) / len(cluster)
                    if _distance_m(lat, lon, centre_lat, centre_lon) <= 3000.0:
                        cluster.append(segment)
                        assigned = True
                        break
                if not assigned:
                    clusters.append([segment])
            for index, cluster in enumerate(clusters):
                label = str(
                    cluster[0].get("name") or cluster[0].get("name_it") or name
                )
                lat = sum(float(segment["lat"]) for segment in cluster) / len(cluster)
                lon = sum(float(segment["lon"]) for segment in cluster) / len(cluster)
                digest = hashlib.sha1(
                    f"{name}|{index}|{len(cluster)}".encode("utf-8")
                ).hexdigest()[:16]
                candidate_id = f"osm:way-group:{digest}"
                if len(cluster) == 1:
                    candidate_id = f"osm:way:{cluster[0]['osm_key']}"
                result.append(
                    PlaceCandidate(
                        candidate_id=candidate_id,
                        label=label,
                        lat=lat,
                        lon=lon,
                        source="way",
                        approximate=True,
                        detail=(
                            f"strada con {len(cluster)} segmenti OSM"
                            + (
                                f" (gruppo {index + 1}/{len(clusters)})"
                                if len(clusters) > 1
                                else ""
                            )
                        ),
                        score=self._score(label, query, "way", lat=lat, lon=lon),
                    )
                )
        return result

    def _by_id(self, candidate_id: str, role: str) -> PlaceCandidate | None:
        if candidate_id == "client:location":
            return None
        if candidate_id.startswith("gtfs:"):
            _, _, _, entity_id = candidate_id.split(":", 3)
            rows = self._fetchall(
                """
                SELECT entity_key AS candidate_id, display_name AS label,
                       dataset_key, entity_id, mode
                FROM public.reference_entities
                WHERE entity_key = %s AND is_current
                """,
                (candidate_id,),
            )
            if not rows:
                return None
            row = rows[0]
            dataset = str(row["dataset_key"])
            schema = self._gtfs_schemas.get(dataset)
            if not schema:
                return None
            stop = self._fetchall(
                f"""
                SELECT ST_Y(stop_loc::geometry) AS lat, ST_X(stop_loc::geometry) AS lon
                FROM "{schema}".stops WHERE stop_id = %s
                """,
                (entity_id,),
            )
            if not stop:
                return None
            return PlaceCandidate(
                candidate_id=candidate_id,
                label=str(row["label"]),
                lat=float(stop[0]["lat"]),
                lon=float(stop[0]["lon"]),
                source="stop",
            )
        if candidate_id.startswith("osm:poi:"):
            rows = self._fetchall(
                f"""
                SELECT 'osm:poi:' || osm_key AS candidate_id,
                       coalesce(name, name_it, osm_key) AS label,
                       ST_Y(label_point::geometry) AS lat,
                       ST_X(label_point::geometry) AS lon,
                       category
                FROM "{self._osm_schema}".pois
                WHERE osm_key = %s AND is_current
                """,
                (candidate_id.removeprefix("osm:poi:"),),
            )
            if not rows:
                return None
            row = rows[0]
            return PlaceCandidate(
                candidate_id=candidate_id,
                label=str(row["label"]),
                lat=float(row["lat"]),
                lon=float(row["lon"]),
                source="poi",
                detail=row.get("category"),
            )
        if candidate_id.startswith("osm:way:"):
            rows = self._fetchall(
                f"""
                SELECT 'osm:way:' || osm_key AS candidate_id,
                       coalesce(name, name_it, osm_key) AS label,
                       ST_Y(ST_LineInterpolatePoint(geom, 0.5)) AS lat,
                       ST_X(ST_LineInterpolatePoint(geom, 0.5)) AS lon
                FROM "{self._osm_schema}".osm_ways
                WHERE osm_key = %s AND is_current
                """,
                (candidate_id.removeprefix("osm:way:"),),
            )
            if not rows:
                return None
            row = rows[0]
            return PlaceCandidate(
                candidate_id=candidate_id,
                label=str(row["label"]),
                lat=float(row["lat"]),
                lon=float(row["lon"]),
                source="way",
                approximate=True,
            )
        return None

    def _nominatim(self, query: str) -> list[PlaceCandidate]:
        if self._config.geocoder_provider != "nominatim":
            return []
        try:
            params = {
                "q": query,
                "format": "jsonv2",
                "limit": self._config.geocoder_max_results,
                "countrycodes": "it",
                "accept-language": "it",
            }
            headers = {"User-Agent": self._config.ingestion_user_agent}
            if self._http_client is not None:
                response = self._http_client.get(
                    f"{self._config.geocoder_base_url.rstrip('/')}/search",
                    params=params,
                    headers=headers,
                    timeout=self._config.geocoder_timeout_s,
                )
            else:
                with httpx.Client(timeout=self._config.geocoder_timeout_s) as client:
                    response = client.get(
                        f"{self._config.geocoder_base_url.rstrip('/')}/search",
                        params=params,
                        headers=headers,
                    )
            if response.status_code >= 400:
                return []
            payload = response.json()
        except (httpx.HTTPError, ValueError):
            return []
        if not isinstance(payload, list):
            return []
        result = []
        for item in payload[: self._config.geocoder_max_results]:
            try:
                result.append(
                    PlaceCandidate(
                        candidate_id=f"nominatim:{item.get('osm_type')}:{item.get('osm_id')}",
                        label=str(item.get("display_name") or query),
                        lat=float(item["lat"]),
                        lon=float(item["lon"]),
                        source="nominatim",
                        approximate=True,
                        detail="geocodifica esterna Nominatim",
                        score=0.7,
                    )
                )
            except (KeyError, TypeError, ValueError):
                continue
        return result

    def resolve(
        self,
        text: str,
        role: str,
        *,
        client_location: Coordinate | None = None,
        selected_candidate_id: str | None = None,
    ) -> PlaceResolution:
        normalized = normalize(text)
        if not normalized:
            return PlaceResolution("not_found", message="Luogo vuoto.")
        if normalized in {
            "qui",
            "qua",
            "da qui",
            "dalla mia posizione",
            "posizione attuale",
            "dove sono",
        }:
            if client_location is None:
                return PlaceResolution(
                    "needs_client_location",
                    message="Per 'da qui' servono le coordinate condivise dal client.",
                )
            return PlaceResolution(
                "resolved",
                place=ResolvedPlace(
                    role=role,  # type: ignore[arg-type]
                    label="Posizione condivisa dal client",
                    lat=client_location.lat,
                    lon=client_location.lon,
                    source="client",
                    entity_id="client:location",
                    approximate=False,
                    detail="coordinate fornite dal client; precisione non dichiarata",
                ),
            )

        if selected_candidate_id:
            if selected_candidate_id == "client:location" and client_location is not None:
                return PlaceResolution(
                    "resolved",
                    place=ResolvedPlace(
                        role=role,  # type: ignore[arg-type]
                        label="Posizione condivisa dal client",
                        lat=client_location.lat,
                        lon=client_location.lon,
                        source="client",
                        entity_id="client:location",
                    ),
                )
            selected = self._by_id(selected_candidate_id, role)
            if selected is not None:
                return PlaceResolution(
                    "resolved",
                    place=ResolvedPlace(
                        role=role,  # type: ignore[arg-type]
                        label=selected.label,
                        lat=selected.lat,
                        lon=selected.lon,
                        source=selected.source,
                        entity_id=selected.candidate_id,
                        approximate=selected.approximate,
                        detail=selected.detail,
                    ),
                )

        query, preferred = self._prepare_query(text)
        patterns = self._patterns(query)
        stops = self._candidate_from_rows(self._stop_rows(patterns), "stop", query)
        pois = self._candidate_from_rows(self._poi_rows(patterns), "poi", query)
        ways = self._group_ways(self._way_rows(patterns), query)
        candidates = [*stops, *pois, *ways]
        candidates = [candidate for candidate in candidates if candidate.score >= 0.42]
        candidates.sort(key=lambda item: (-item.score, item.source, item.label, item.candidate_id))
        if not candidates:
            external = self._nominatim(query)
            if external:
                if len(external) > 1:
                    return PlaceResolution("ambiguous", candidates=external[:5])
                candidates = external
            else:
                return PlaceResolution(
                    "not_found",
                    message=f"Nessun luogo trovato per '{text}'.",
                )

        if selected_candidate_id:
            selected = next(
                (
                    candidate
                    for candidate in candidates
                    if candidate.candidate_id == selected_candidate_id
                ),
                None,
            )
            if selected is not None:
                return self._resolved(role, selected)

        if preferred:
            preferred_candidates = [
                candidate for candidate in candidates if candidate.source == preferred
            ]
            if preferred_candidates:
                candidates = preferred_candidates

        exact = [candidate for candidate in candidates if candidate.score >= 0.99]
        if len(exact) == 1:
            return self._resolved(role, exact[0])
        if len(exact) > 1:
            # Same street grouped as segments is one place; an exact transit
            # stop wins over an exact polygon only by the documented type
            # priority. Same-name stops in different datasets stay ambiguous.
            exact.sort(key=lambda item: (-item.score, item.candidate_id))
            if exact[0].score - exact[1].score >= 0.01:
                return self._resolved(role, exact[0])
            sources = {candidate.source for candidate in exact}
            # Several OSM elements can represent the same square/polygon; that
            # is one named place, not different places. Same-name transit stops
            # in different datasets remain genuinely ambiguous.
            if sources == {"way"}:
                if len({candidate.candidate_id for candidate in exact}) == 1:
                    return self._resolved(role, exact[0])
                return PlaceResolution("ambiguous", candidates=exact[:8])
            if sources == {"poi"}:
                return self._resolved(role, exact[0])
            return PlaceResolution("ambiguous", candidates=exact[:8])

        if len(candidates) == 1:
            return self._resolved(role, candidates[0])
        top = candidates[0]
        if top.score >= 0.55 and len(candidates) > 1:
            if candidates[1].score + 0.08 < top.score:
                return self._resolved(role, top)
        return PlaceResolution("ambiguous", candidates=candidates[:8])

    @staticmethod
    def _resolved(role: str, candidate: PlaceCandidate) -> PlaceResolution:
        return PlaceResolution(
            "resolved",
            place=ResolvedPlace(
                role=role,  # type: ignore[arg-type]
                label=candidate.label,
                lat=candidate.lat,
                lon=candidate.lon,
                source=candidate.source,
                entity_id=candidate.candidate_id,
                approximate=candidate.approximate,
                detail=candidate.detail,
            ),
            candidates=[candidate],
        )


__all__ = ["PlaceCandidate", "PlaceResolution", "PlaceResolver", "normalize"]
