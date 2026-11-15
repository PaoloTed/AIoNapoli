"""Resolve proposed names to dataset-scoped GTFS entities and OSM roads."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any

from app.config.sources import SourceDefinition
from app.domain.models.disruption import LinkEntityType
from app.services.ingestion.extraction import NewsExtraction

_DATASET_RE = re.compile(r"^[a-z0-9_]+$")
_SCHEMA_RE = re.compile(r"^[a-z_][a-z0-9_]*$")


def normalize_name(value: str) -> str:
    text = unicodedata.normalize("NFKD", value.casefold())
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def normalize_route_ref(value: str) -> str:
    text = normalize_name(value)
    text = re.sub(
        r"\b(linea|line|metropolitana|metro|autobus|autolinea|bus|tram|treno|"
        r"ferroviaria|ferrovia|servizio|navetta|direzione|verso)\b",
        " ",
        text,
    )
    text = re.sub(r"\b(l)\s*(\d+)\b", r"L\2", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text.upper().replace(" ", "")


@dataclass
class ResolvedEntity:
    entity_type: LinkEntityType
    entity_id: str
    dataset_key: str | None
    display_name: str
    raw_reference: str
    status: str
    candidates: list[dict[str, Any]] = field(default_factory=list)
    mode: str | None = None
    details: dict[str, Any] = field(default_factory=dict)

    def link(self) -> dict[str, Any]:
        return {
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "dataset_key": self.dataset_key,
            "raw_reference": self.raw_reference,
            "mode": self.mode,
            "details": {**self.details, "resolution_status": self.status},
        }


@dataclass
class ResolutionResult:
    links: list[ResolvedEntity]
    unresolved: list[str]
    ambiguous: list[str]
    datasets: set[str]

    def has_resolved(self) -> bool:
        return any(link.status == "resolved" for link in self.links)


class EntityResolver:
    """Parameterized search on the existing reference/GTFS/OSM catalogues."""

    def __init__(
        self,
        conn: Any,
        *,
        gtfs_schemas: dict[str, str],
        osm_schema: str = "osm_territory",
    ) -> None:
        if not _SCHEMA_RE.fullmatch(osm_schema):
            raise ValueError(f"schema OSM non valido: {osm_schema!r}")
        for key, schema in gtfs_schemas.items():
            if not _DATASET_RE.fullmatch(key) or not _SCHEMA_RE.fullmatch(schema):
                raise ValueError(f"dataset GTFS non valido: {key}:{schema}")
        self._conn = conn
        self._gtfs_schemas = dict(gtfs_schemas)
        self._osm_schema = osm_schema
        self._operator_by_dataset = self._load_operator_metadata()

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

    def _load_operator_metadata(self) -> dict[str, dict[str, str]]:
        rows = self._fetchall(
            """
            SELECT dataset_key, operator_id, operator_name, agency_ids
            FROM gtfs_datasets WHERE is_active
            """
        )
        result: dict[str, dict[str, str]] = {}
        for row in rows:
            result[str(row["dataset_key"])] = {
                "operator_id": str(row.get("operator_id") or ""),
                "operator_name": str(row.get("operator_name") or ""),
                "agency_ids": str(row.get("agency_ids") or ""),
            }
        return result

    def dataset_hint(self, extraction: NewsExtraction, source: SourceDefinition) -> str | None:
        text = normalize_name(
            " ".join(
                [
                    *extraction.operator_names,
                    source.operator or "",
                    source.name,
                ]
            )
        )
        if re.search(r"\banm\b|azienda napoletana", text):
            return "anm" if "anm" in self._gtfs_schemas else None
        if re.search(r"\beav\b", text):
            return "eav" if "eav" in self._gtfs_schemas else None
        if source.operator and source.operator in self._gtfs_schemas:
            return source.operator
        # A route name that exists in exactly one configured dataset is enough
        # to select it; this is not a default to EAV.
        return None

    def _reference_rows(
        self,
        entity_type: str,
        *,
        dataset_key: str | None,
        exact: str,
    ) -> list[dict[str, Any]]:
        params: list[Any] = [entity_type]
        where = "entity_type = %s AND is_current"
        if dataset_key:
            where += " AND dataset_key = %s"
            params.append(dataset_key)
        params.extend([exact, exact])
        return self._fetchall(
            f"""
            SELECT entity_key, dataset_key, entity_type, entity_id, display_name, mode
            FROM reference_entities
            WHERE {where}
              AND (lower(display_name) = lower(%s) OR entity_id = %s)
            ORDER BY dataset_key, entity_id
            LIMIT 30
            """,
            tuple(params),
        )

    def resolve_route(self, reference: str, *, dataset_key: str | None) -> ResolvedEntity:
        normalized = normalize_route_ref(reference)
        raw = reference.strip()
        exact_values = {raw, normalized}
        candidates: dict[str, dict[str, Any]] = {}
        for exact in exact_values:
            for row in self._reference_rows("route", dataset_key=dataset_key, exact=exact):
                candidates[row["entity_key"]] = row
        if not candidates and normalized:
            params: list[Any] = ["route"]
            where = "entity_type = %s AND is_current"
            if dataset_key:
                where += " AND dataset_key = %s"
                params.append(dataset_key)
            params.append(f"%{normalized}%")
            for row in self._fetchall(
                f"""
                SELECT entity_key, dataset_key, entity_type, entity_id, display_name, mode
                FROM reference_entities
                WHERE {where} AND upper(replace(display_name, ' ', '')) LIKE %s
                ORDER BY dataset_key, entity_id LIMIT 30
                """,
                tuple(params),
            ):
                candidates[row["entity_key"]] = row
        return self._entity_result(LinkEntityType.ROUTE, reference, dataset_key, candidates)

    def resolve_stop(self, reference: str, *, dataset_key: str | None) -> ResolvedEntity:
        candidates: dict[str, dict[str, Any]] = {}
        for exact in {reference.strip(), normalize_name(reference)}:
            for row in self._reference_rows("stop", dataset_key=dataset_key, exact=exact):
                candidates[row["entity_key"]] = row
        if not candidates:
            params: list[Any] = ["stop"]
            where = "entity_type = %s AND is_current"
            if dataset_key:
                where += " AND dataset_key = %s"
                params.append(dataset_key)
            params.append(f"%{normalize_name(reference)}%")
            for row in self._fetchall(
                f"""
                SELECT entity_key, dataset_key, entity_type, entity_id, display_name, mode
                FROM reference_entities
                WHERE {where} AND lower(display_name) LIKE %s
                ORDER BY length(display_name), dataset_key, entity_id LIMIT 30
                """,
                tuple(params),
            ):
                candidates[row["entity_key"]] = row
        return self._entity_result(LinkEntityType.STOP, reference, dataset_key, candidates)

    def resolve_trip(self, reference: str, *, dataset_key: str | None) -> ResolvedEntity:
        candidates: dict[str, dict[str, Any]] = {}
        for row in self._reference_rows("trip", dataset_key=dataset_key, exact=reference.strip()):
            candidates[row["entity_key"]] = row
        return self._entity_result(LinkEntityType.TRIP, reference, dataset_key, candidates)

    def _entity_result(
        self,
        entity_type: LinkEntityType,
        reference: str,
        dataset_key: str | None,
        candidates: dict[str, dict[str, Any]],
    ) -> ResolvedEntity:
        values = list(candidates.values())
        if len(values) == 1:
            row = values[0]
            return ResolvedEntity(
                entity_type=entity_type,
                entity_id=str(row["entity_id"]),
                dataset_key=str(row["dataset_key"]),
                display_name=str(row.get("display_name") or row["entity_id"]),
                raw_reference=reference,
                status="resolved",
                mode=row.get("mode"),
            )
        if len(values) > 1:
            return ResolvedEntity(
                entity_type=entity_type,
                entity_id=reference,
                dataset_key=dataset_key,
                display_name=reference,
                raw_reference=reference,
                status="ambiguous",
                candidates=[
                    {
                        "entity_id": row["entity_id"],
                        "dataset_key": row["dataset_key"],
                        "display_name": row.get("display_name"),
                    }
                    for row in values[:10]
                ],
            )
        return ResolvedEntity(
            entity_type=entity_type,
            entity_id=reference,
            dataset_key=dataset_key,
            display_name=reference,
            raw_reference=reference,
            status="unresolved",
        )

    def resolve_road(self, reference: str) -> list[ResolvedEntity]:
        name = reference.strip()
        normalized = normalize_name(name)
        if not normalized:
            return []
        rows = self._fetchall(
            f"""
            SELECT osm_key, name, name_it, ref, highway, tunnel, bridge, layer
            FROM {self._osm_schema}.osm_ways
            WHERE is_current
              AND (lower(name) = lower(%s) OR lower(name_it) = lower(%s)
                   OR lower(ref) = lower(%s))
            ORDER BY osm_key
            LIMIT 80
            """,
            (name, name, name),
        )
        if not rows:
            rows = self._fetchall(
                f"""
                SELECT osm_key, name, name_it, ref, highway, tunnel, bridge, layer
                FROM {self._osm_schema}.osm_ways
                WHERE is_current
                  AND (lower(name) LIKE %s OR lower(name_it) LIKE %s)
                ORDER BY length(coalesce(name, name_it, '')), osm_key
                LIMIT 40
                """,
                (f"%{name}%", f"%{name}%"),
            )
            distinct_names = {
                normalize_name(str(row.get("name") or row.get("name_it") or ""))
                for row in rows
                if row.get("name") or row.get("name_it")
            }
            if len(distinct_names) > 1:
                return [
                    ResolvedEntity(
                        entity_type=LinkEntityType.OSM_WAY,
                        entity_id=name,
                        dataset_key=None,
                        display_name=name,
                        raw_reference=name,
                        status="ambiguous",
                        candidates=[
                            {"entity_id": row["osm_key"], "display_name": row.get("name")}
                            for row in rows[:10]
                        ],
                    )
                ]
        if not rows:
            return [
                ResolvedEntity(
                    entity_type=LinkEntityType.OSM_WAY,
                    entity_id=name,
                    dataset_key=None,
                    display_name=name,
                    raw_reference=name,
                    status="unresolved",
                )
            ]
        if len(rows) > 1:
            # A road is normally split into several OSM ways. They are one
            # named place, not different places: preserve the group explicitly.
            display = str(rows[0].get("name") or rows[0].get("name_it") or name)
            return [
                ResolvedEntity(
                    entity_type=LinkEntityType.OSM_WAY,
                    entity_id=str(row["osm_key"]),
                    dataset_key=None,
                    display_name=display,
                    raw_reference=name,
                    status="resolved",
                    mode="road",
                    details={
                        "street_group": display,
                        "segment_index": index,
                        "segment_count": len(rows),
                        "highway": row.get("highway"),
                        "tunnel": row.get("tunnel"),
                        "bridge": row.get("bridge"),
                        "layer": row.get("layer"),
                    },
                )
                for index, row in enumerate(rows[:40])
            ]
        row = rows[0]
        return [
            ResolvedEntity(
                entity_type=LinkEntityType.OSM_WAY,
                entity_id=str(row["osm_key"]),
                dataset_key=None,
                display_name=str(row.get("name") or row.get("name_it") or name),
                raw_reference=name,
                status="resolved",
                mode="road",
                details={
                    "street_group": row.get("name") or row.get("name_it"),
                    "segment_index": 0,
                    "segment_count": 1,
                    "highway": row.get("highway"),
                    "tunnel": row.get("tunnel"),
                    "bridge": row.get("bridge"),
                    "layer": row.get("layer"),
                },
            )
        ]

    def resolve_poi(self, reference: str) -> list[ResolvedEntity]:
        name = reference.strip()
        rows = self._fetchall(
            f"""
            SELECT osm_key, name, name_it, category, category_value
            FROM {self._osm_schema}.pois
            WHERE is_current AND (lower(name) = lower(%s) OR lower(name_it) = lower(%s))
            ORDER BY osm_key LIMIT 20
            """,
            (name, name),
        )
        if not rows:
            rows = self._fetchall(
                f"""
                SELECT osm_key, name, name_it, category, category_value
                FROM {self._osm_schema}.pois
                WHERE is_current AND (lower(name) LIKE %s OR lower(name_it) LIKE %s)
                ORDER BY length(coalesce(name, name_it, '')), osm_key LIMIT 20
                """,
                (f"%{name}%", f"%{name}%"),
            )
        if not rows:
            return [
                ResolvedEntity(
                    entity_type=LinkEntityType.OSM_POI,
                    entity_id=name,
                    dataset_key=None,
                    display_name=name,
                    raw_reference=name,
                    status="unresolved",
                )
            ]
        if len(rows) > 1:
            return [
                ResolvedEntity(
                    entity_type=LinkEntityType.OSM_POI,
                    entity_id=name,
                    dataset_key=None,
                    display_name=name,
                    raw_reference=name,
                    status="ambiguous",
                    candidates=[
                        {"entity_id": candidate["osm_key"], "display_name": candidate.get("name")}
                        for candidate in rows[:10]
                    ],
                )
            ]
        row = rows[0]
        return [
            ResolvedEntity(
                entity_type=LinkEntityType.OSM_POI,
                entity_id=str(row["osm_key"]),
                dataset_key=None,
                display_name=str(row.get("name") or row.get("name_it") or name),
                raw_reference=name,
                status="resolved",
            )
        ]

    def resolve_extraction(
        self, extraction: NewsExtraction, source: SourceDefinition
    ) -> ResolutionResult:
        hint = self.dataset_hint(extraction, source)
        links: list[ResolvedEntity] = []
        unresolved: list[str] = []
        ambiguous: list[str] = []
        datasets: set[str] = set()

        for ref in extraction.route_refs:
            entity = self.resolve_route(ref, dataset_key=hint)
            links.append(entity)
            if entity.status != "resolved":
                (ambiguous if entity.status == "ambiguous" else unresolved).append(f"route:{ref}")
            if entity.dataset_key:
                datasets.add(entity.dataset_key)
        for ref in extraction.trip_refs:
            entity = self.resolve_trip(ref, dataset_key=hint)
            links.append(entity)
            if entity.status != "resolved":
                (ambiguous if entity.status == "ambiguous" else unresolved).append(f"trip:{ref}")
            if entity.dataset_key:
                datasets.add(entity.dataset_key)
        for ref in extraction.stop_refs:
            entity = self.resolve_stop(ref, dataset_key=hint)
            links.append(entity)
            if entity.status != "resolved":
                (ambiguous if entity.status == "ambiguous" else unresolved).append(f"stop:{ref}")
            if entity.dataset_key:
                datasets.add(entity.dataset_key)
        road_groups: dict[str, list[ResolvedEntity]] = {}
        for ref in extraction.road_refs:
            road_entities = self.resolve_road(ref)
            if not road_entities:
                unresolved.append(f"road:{ref}")
                continue
            for entity in road_entities:
                road_groups.setdefault(ref, []).append(entity)
                if entity.status != "resolved":
                    (ambiguous if entity.status == "ambiguous" else unresolved).append(
                        f"road:{ref}"
                    )
        for entities in road_groups.values():
            links.extend(entities)
        for ref in extraction.place_names:
            # Place names are used as a geographic hint only when no explicit
            # GTFS/road entity was resolved; POIs are the least ambiguous.
            if extraction.stop_refs or extraction.road_refs or extraction.route_refs:
                continue
            poi_entities = self.resolve_poi(ref)
            links.extend(poi_entities)
            if all(entity.status != "resolved" for entity in poi_entities):
                unresolved.append(f"place:{ref}")

        # Stable de-duplication of links by type/id/dataset.
        unique: dict[tuple[str, str, str | None], ResolvedEntity] = {}
        for link in links:
            unique[(link.entity_type.value, link.entity_id, link.dataset_key)] = link
        return ResolutionResult(
            links=list(unique.values()),
            unresolved=unresolved,
            ambiguous=ambiguous,
            datasets=datasets,
        )


__all__ = [
    "EntityResolver",
    "ResolutionResult",
    "ResolvedEntity",
    "normalize_name",
    "normalize_route_ref",
]
