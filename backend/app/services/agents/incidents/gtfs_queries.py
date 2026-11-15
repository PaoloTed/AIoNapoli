"""Targeted, read-only GTFS queries for incident evaluation.

The incident agent must not load an entire feed per request. These helpers keep
dataset selection explicit and understand GTFS times beyond 24:00 by working on
``stop_times`` intervals and service days.
"""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from typing import Any

_SCHEMA_RE = re.compile(r"^[a-z_][a-z0-9_]*$")
_DATASET_RE = re.compile(r"^[a-z0-9_]+$")


def interval_seconds(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, timedelta):
        return int(value.total_seconds())
    if isinstance(value, (int, float)):
        return int(value)
    text = str(value).strip()
    if not text:
        return None
    sign = -1 if text.startswith("-") else 1
    if text[0] in "+-":
        text = text[1:]
    parts = text.split(":")
    try:
        if len(parts) == 3:
            hours, minutes, seconds = (int(part) for part in parts)
            return sign * (hours * 3600 + minutes * 60 + seconds)
        if len(parts) == 2:
            hours, minutes = (int(part) for part in parts)
            return sign * (hours * 3600 + minutes * 60)
        return sign * int(float(text))
    except ValueError:
        return None


def seconds_to_gtfs(value: int | None) -> str | None:
    if value is None:
        return None
    sign = "-" if value < 0 else ""
    total = abs(value)
    hours, rem = divmod(total, 3600)
    minutes, seconds = divmod(rem, 60)
    return f"{sign}{hours:02d}:{minutes:02d}:{seconds:02d}"


class GtfsQueries:
    def __init__(self, conn: Any, schemas: dict[str, str]) -> None:
        for key, schema in schemas.items():
            if not _DATASET_RE.fullmatch(key) or not _SCHEMA_RE.fullmatch(schema):
                raise ValueError(f"dataset GTFS non valido: {key}:{schema}")
        self._conn = conn
        self._schemas = dict(schemas)
        self._cache: dict[tuple[str, ...], Any] = {}

    def has_dataset(self, dataset_key: str) -> bool:
        return dataset_key in self._schemas

    def schema(self, dataset_key: str) -> str:
        try:
            return self._schemas[dataset_key]
        except KeyError as exc:
            raise KeyError(f"dataset GTFS non configurato: {dataset_key}") from exc

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

    def _cached(self, key: tuple[str, ...], loader: Any) -> Any:
        if key not in self._cache:
            self._cache[key] = loader()
        return self._cache[key]

    def route(self, dataset: str, route_id: str) -> dict[str, Any] | None:
        return self._cached(
            ("route", dataset, route_id),
            lambda: (
                self._fetchall(
                    f"""
                    SELECT route_id, route_short_name, route_long_name,
                           route_type::text::integer AS route_type
                    FROM "{self.schema(dataset)}".routes
                    WHERE route_id = %s
                    """,
                    (route_id,),
                )
                or [None]
            )[0],
        )

    def trip(self, dataset: str, trip_id: str) -> dict[str, Any] | None:
        return self._cached(
            ("trip", dataset, trip_id),
            lambda: (
                self._fetchall(
                    f"""
                    SELECT trip_id, route_id, service_id, trip_headsign,
                           direction_id, shape_id
                    FROM "{self.schema(dataset)}".trips
                    WHERE trip_id = %s
                    """,
                    (trip_id,),
                )
                or [None]
            )[0],
        )

    def stop_times(self, dataset: str, trip_id: str) -> list[dict[str, Any]]:
        def load() -> list[dict[str, Any]]:
            rows = self._fetchall(
                f"""
                SELECT stop_id, stop_sequence, arrival_time, departure_time
                FROM "{self.schema(dataset)}".stop_times
                WHERE trip_id = %s
                ORDER BY stop_sequence
                """,
                (trip_id,),
            )
            for row in rows:
                row["arrival_s"] = interval_seconds(row.get("arrival_time"))
                row["departure_s"] = interval_seconds(row.get("departure_time"))
                row["arrival_time"] = seconds_to_gtfs(row["arrival_s"])
                row["departure_time"] = seconds_to_gtfs(row["departure_s"])
            return rows

        return self._cached(("stop_times", dataset, trip_id), load)

    def service_dates(
        self,
        dataset: str,
        service_id: str,
        start: date,
        end: date,
    ) -> set[date]:
        def load() -> set[date]:
            rows = self._fetchall(
                f"""
                SELECT date FROM "{self.schema(dataset)}".service_days
                WHERE service_id = %s AND date >= %s AND date <= %s
                """,
                (service_id, start, end),
            )
            result: set[date] = set()
            for row in rows:
                value = row["date"]
                if isinstance(value, datetime):
                    result.add(value.date())
                elif isinstance(value, date):
                    result.add(value)
                else:
                    result.add(date.fromisoformat(str(value)[:10]))
            return result

        return self._cached(
            ("service_dates", dataset, service_id, start.isoformat(), end.isoformat()), load
        )

    def trip_active_on(self, dataset: str, trip_id: str, service_date: date) -> bool | None:
        trip = self.trip(dataset, trip_id)
        if trip is None:
            return None
        dates = self.service_dates(
            dataset,
            str(trip["service_id"]),
            service_date,
            service_date,
        )
        return service_date in dates

    def stop(self, dataset: str, stop_id: str) -> dict[str, Any] | None:
        return self._cached(
            ("stop", dataset, stop_id),
            lambda: (
                self._fetchall(
                    f"""
                    SELECT stop_id, stop_name,
                           ST_Y(stop_loc::geometry) AS lat,
                           ST_X(stop_loc::geometry) AS lon
                    FROM "{self.schema(dataset)}".stops
                    WHERE stop_id = %s
                    """,
                    (stop_id,),
                )
                or [None]
            )[0],
        )

    def routes_serving_stop(self, dataset: str, stop_id: str, limit: int = 100) -> list[str]:
        rows = self._fetchall(
            f"""
            SELECT DISTINCT t.route_id
            FROM "{self.schema(dataset)}".stop_times st
            JOIN "{self.schema(dataset)}".trips t ON t.trip_id = st.trip_id
            WHERE st.stop_id = %s
            ORDER BY t.route_id
            LIMIT %s
            """,
            (stop_id, max(1, min(limit, 500))),
        )
        return [str(row["route_id"]) for row in rows]

    def trip_stop_sequences(self, dataset: str, trip_id: str) -> dict[str, int]:
        return {
            str(row["stop_id"]): int(row["stop_sequence"])
            for row in self.stop_times(dataset, trip_id)
        }


__all__ = ["GtfsQueries", "interval_seconds", "seconds_to_gtfs"]
