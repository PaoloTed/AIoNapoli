"""Read-only access to the OSM territory catalogue in PostgreSQL/PostGIS.

This repository is a catalogue, not a geocoder and not a routing graph. It
returns OSM ways and POIs with their original geometry and stable ``osm_key``
(``node/123``, ``way/456``, ``relation/789``). Distances are computed with
PostGIS geography, so results are in metres.
"""

from __future__ import annotations

import re
from typing import Any

_SCHEMA_RE = re.compile(r"^[a-z_][a-z0-9_]*$")


class OSMTerritoryRepository:
    """Parameterized search/read access to ``osm_territory``."""

    def __init__(
        self,
        conn: Any,
        *,
        schema: str = "osm_territory",
        dataset_key: str = "osm_napoli",
    ) -> None:
        if not _SCHEMA_RE.match(schema):
            raise ValueError(f"schema territorio non valido: {schema!r}")
        self._conn = conn
        self._schema = schema
        self._dataset_key = dataset_key

    def _row_to_dict(self, cur: Any, row: Any) -> dict[str, Any]:
        if isinstance(row, dict):
            return dict(row)
        if hasattr(row, "keys"):
            return {k: row[k] for k in row.keys()}
        cols = [desc[0] for desc in cur.description]
        return dict(zip(cols, row))

    def _fetchall(self, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        cur = self._conn.cursor()
        cur.execute(sql, params)
        return [self._row_to_dict(cur, row) for row in cur.fetchall()]

    def get_dataset_info(self) -> dict[str, Any] | None:
        rows = self._fetchall(
            """
            SELECT dataset_key, source_url, source_sha256, dataset_version,
                   osm_snapshot, osm_timestamp, attribution, importer_name,
                   importer_version, imported_at, published_at, row_counts,
                   is_active
            FROM osm_datasets
            WHERE dataset_key = %s AND is_active = TRUE
            ORDER BY published_at DESC
            LIMIT 1
            """,
            (self._dataset_key,),
        )
        return rows[0] if rows else None

    def search_ways(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        """Search OSM ways by name/ref, returning multiple candidates."""
        text = str(query).strip()
        if not text:
            raise ValueError("query non può essere vuota")
        if limit < 1 or limit > 100:
            raise ValueError("limit deve essere tra 1 e 100")
        pattern = f"%{text}%"
        return self._fetchall(
            f"""
            SELECT osm_key, osm_type, osm_id, name, name_it, ref, highway,
                   access, foot, bicycle, motor_vehicle, oneway, bridge, tunnel,
                   layer, surface, service, maxspeed, lanes, width, tags,
                   ST_AsText(geom) AS geometry,
                   ST_X(ST_LineInterpolatePoint(geom, 0.5)) AS longitude,
                   ST_Y(ST_LineInterpolatePoint(geom, 0.5)) AS latitude,
                   dataset_version, osm_version, osm_timestamp, is_current
            FROM "{self._schema}".osm_ways
            WHERE is_current
              AND (lower(name) LIKE lower(%s) OR lower(ref) LIKE lower(%s))
            ORDER BY
              CASE
                WHEN lower(name) = lower(%s) THEN 0
                WHEN lower(name) LIKE lower(%s) || '%%' THEN 1
                ELSE 2
              END,
              name NULLS LAST,
              osm_key
            LIMIT %s
            """,
            (pattern, pattern, text, text, limit),
        )

    def get_way(self, osm_key: str) -> dict[str, Any] | None:
        rows = self._fetchall(
            f"""
            SELECT osm_key, osm_type, osm_id, name, name_it, ref, highway,
                   access, foot, bicycle, motor_vehicle, vehicle, oneway,
                   junction, bridge, tunnel, layer, surface, service, maxspeed,
                   lanes, width, tracktype, smoothness, wheelchair, incline,
                   sidewalk, cycleway, footway, segregated, construction, route,
                   tags, ST_AsText(geom) AS geometry,
                   ST_X(ST_LineInterpolatePoint(geom, 0.5)) AS longitude,
                   ST_Y(ST_LineInterpolatePoint(geom, 0.5)) AS latitude,
                   source_id, dataset_version, osm_version, osm_timestamp,
                   ingested_at, is_current, first_seen_at, last_seen_at
            FROM "{self._schema}".osm_ways
            WHERE osm_key = %s AND is_current
            """,
            (str(osm_key),),
        )
        return rows[0] if rows else None

    def search_pois(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        """Search OSM POIs by name/ref, returning multiple candidates."""
        text = str(query).strip()
        if not text:
            raise ValueError("query non può essere vuota")
        if limit < 1 or limit > 100:
            raise ValueError("limit deve essere tra 1 e 100")
        pattern = f"%{text}%"
        return self._fetchall(
            f"""
            SELECT osm_key, osm_type, osm_id, name, name_it, ref, operator,
                   brand, addr_street, addr_housenumber, addr_city, phone,
                   website, opening_hours, wheelchair, category, category_value,
                   tags, ST_AsText(geom) AS geometry,
                   ST_AsText(label_point) AS label_point,
                   ST_X(label_point) AS longitude, ST_Y(label_point) AS latitude,
                   dataset_version, osm_version, osm_timestamp, is_current
            FROM "{self._schema}".pois
            WHERE is_current
              AND (lower(name) LIKE lower(%s) OR lower(ref) LIKE lower(%s))
            ORDER BY
              CASE
                WHEN lower(name) = lower(%s) THEN 0
                WHEN lower(name) LIKE lower(%s) || '%%' THEN 1
                ELSE 2
              END,
              name NULLS LAST,
              osm_key
            LIMIT %s
            """,
            (pattern, pattern, text, text, limit),
        )

    def get_poi(self, osm_key: str) -> dict[str, Any] | None:
        rows = self._fetchall(
            f"""
            SELECT osm_key, osm_type, osm_id, name, name_it, ref, operator,
                   brand, addr_street, addr_housenumber, addr_city, phone,
                   website, opening_hours, wheelchair, category, category_value,
                   tags, ST_AsText(geom) AS geometry,
                   ST_AsText(label_point) AS label_point,
                   ST_X(label_point) AS longitude, ST_Y(label_point) AS latitude,
                   source_id, dataset_version, osm_version, osm_timestamp,
                   ingested_at, is_current, first_seen_at, last_seen_at
            FROM "{self._schema}".pois
            WHERE osm_key = %s AND is_current
            """,
            (str(osm_key),),
        )
        return rows[0] if rows else None

    @staticmethod
    def _check_lonlat(lon: float, lat: float) -> None:
        if not (-180.0 <= lon <= 180.0 and -90.0 <= lat <= 90.0):
            raise ValueError("coordinate fuori range WGS84")

    def find_ways_near(
        self, lon: float, lat: float, radius_m: float = 500.0, limit: int = 20
    ) -> list[dict[str, Any]]:
        """Return ways within ``radius_m`` metres, ordered by distance."""
        self._check_lonlat(float(lon), float(lat))
        if radius_m <= 0:
            raise ValueError("radius_m deve essere positivo")
        if limit < 1 or limit > 100:
            raise ValueError("limit deve essere tra 1 e 100")
        return self._fetchall(
            f"""
            WITH origin AS (
                SELECT ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography AS g
            )
            SELECT w.osm_key, w.osm_type, w.osm_id, w.name, w.ref, w.highway,
                   w.tags, ST_AsText(w.geom) AS geometry,
                   ST_Distance(w.geom::geography, origin.g) AS distance_m,
                   w.dataset_version
            FROM "{self._schema}".osm_ways w CROSS JOIN origin
            WHERE w.is_current
              AND ST_DWithin(w.geom::geography, origin.g, %s)
            ORDER BY distance_m, w.osm_key
            LIMIT %s
            """,
            (float(lon), float(lat), float(radius_m), limit),
        )

    def find_pois_near(
        self, lon: float, lat: float, radius_m: float = 500.0, limit: int = 20
    ) -> list[dict[str, Any]]:
        """Return POIs within ``radius_m`` metres, using the label point."""
        self._check_lonlat(float(lon), float(lat))
        if radius_m <= 0:
            raise ValueError("radius_m deve essere positivo")
        if limit < 1 or limit > 100:
            raise ValueError("limit deve essere tra 1 e 100")
        return self._fetchall(
            f"""
            WITH origin AS (
                SELECT ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography AS g
            )
            SELECT p.osm_key, p.osm_type, p.osm_id, p.name, p.ref, p.category,
                   p.category_value, p.tags, ST_AsText(p.geom) AS geometry,
                   ST_X(p.label_point) AS longitude, ST_Y(p.label_point) AS latitude,
                   ST_Distance(p.label_point::geography, origin.g) AS distance_m,
                   p.dataset_version
            FROM "{self._schema}".pois p CROSS JOIN origin
            WHERE p.is_current
              AND ST_DWithin(p.label_point::geography, origin.g, %s)
            ORDER BY distance_m, p.osm_key
            LIMIT %s
            """,
            (float(lon), float(lat), float(radius_m), limit),
        )

    def get_ways_by_keys(self, keys: list[str]) -> list[dict[str, Any]]:
        """Read several OSM ways in one query, preserving geometry as WKT."""
        values = [str(key) for key in keys if str(key).strip()]
        if not values:
            return []
        return self._fetchall(
            f"""
            SELECT osm_key, name, name_it, ref, highway, access, foot, bicycle,
                   motor_vehicle, oneway, bridge, tunnel, layer, surface, tags,
                   ST_AsText(geom) AS geometry, dataset_version, is_current
            FROM "{self._schema}".osm_ways
            WHERE osm_key = ANY(%s) AND is_current
            ORDER BY osm_key
            """,
            (values,),
        )

    def measure_corridor_overlap(
        self,
        way_key: str,
        line_wkt: str,
        *,
        buffer_m: float = 20.0,
        metric_srid: int = 32633,
    ) -> dict[str, float] | None:
        """Measure how much of a leg runs along one OSM way, in metres.

        A 2D proximity is only a candidate. The caller compares ``overlap_m``
        with a mode-specific threshold before declaring a block.
        """
        if metric_srid <= 0:
            raise ValueError("metric_srid non valido")
        if buffer_m <= 0:
            raise ValueError("buffer_m deve essere positivo")
        rows = self._fetchall(
            f"""
            WITH line AS (
                SELECT ST_Transform(ST_GeomFromText(%s, 4326), %s) AS g
            )
            SELECT ST_Length(
                       ST_Intersection(
                           ST_Buffer(ST_Transform(w.geom, %s), %s),
                           line.g
                       )
                   ) AS overlap_m,
                   ST_Distance(ST_Transform(w.geom, %s), line.g) AS distance_m
            FROM "{self._schema}".osm_ways w CROSS JOIN line
            WHERE w.osm_key = %s AND w.is_current
            """,
            (line_wkt, metric_srid, metric_srid, float(buffer_m), metric_srid, str(way_key)),
        )
        if not rows:
            return None
        return {
            "overlap_m": float(rows[0]["overlap_m"] or 0.0),
            "distance_m": float(rows[0]["distance_m"] or 0.0),
        }

    def find_ways_intersecting(
        self,
        min_lon: float,
        min_lat: float,
        max_lon: float,
        max_lat: float,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Return ways intersecting an explicit WGS84 bounding box."""
        self._check_lonlat(float(min_lon), float(min_lat))
        self._check_lonlat(float(max_lon), float(max_lat))
        if min_lon >= max_lon or min_lat >= max_lat:
            raise ValueError("bounding box non valido")
        if limit < 1 or limit > 200:
            raise ValueError("limit deve essere tra 1 e 200")
        return self._fetchall(
            f"""
            SELECT osm_key, osm_type, osm_id, name, ref, highway, tags,
                   ST_AsText(geom) AS geometry, dataset_version
            FROM "{self._schema}".osm_ways
            WHERE is_current
              AND ST_Intersects(
                  geom,
                  ST_MakeEnvelope(%s, %s, %s, %s, 4326)
              )
            ORDER BY name NULLS LAST, osm_key
            LIMIT %s
            """,
            (float(min_lon), float(min_lat), float(max_lon), float(max_lat), limit),
        )
