"""Persistent disruption repository with stable GTFS/OSM references.

The authoritative store is the existing ``service_alerts`` table, extended in
migration 004. ``service_alert_links`` references ``reference_entities`` by a
stable key; that catalogue is refreshed from GTFS/OSM without deleting old
rows. No second disruption archive is created.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import date, datetime, timezone
from typing import Any

from app.domain.models.disruption import (
    Direction,
    DisruptionInput,
    DisruptionLinkInput,
    DisruptionLinkRecord,
    DisruptionRecord,
    LifecycleStatus,
    LinkEntityType,
    ResolutionStatus,
)

_SCHEMA_RE = re.compile(r"^[a-z_][a-z0-9_]*$")


class DisruptionRepository:
    """Validated, idempotent persistence for disruptions and their links."""

    def __init__(
        self,
        conn: Any,
        *,
        gtfs_schema: str = "gtfs_eav",
        gtfs_dataset_key: str = "eav",
        osm_dataset_key: str = "osm_napoli",
    ) -> None:
        for schema in (gtfs_schema,):
            if not _SCHEMA_RE.match(schema):
                raise ValueError(f"schema non valido: {schema!r}")
        self._conn = conn
        self._gtfs_schema = gtfs_schema
        self._gtfs_dataset_key = gtfs_dataset_key
        self._osm_dataset_key = osm_dataset_key

    @property
    def conn(self) -> Any:
        """Read-only connection handle for a sibling read-only specialist."""
        return self._conn

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

    @staticmethod
    def _entity_key(entity_type: LinkEntityType, entity_id: str, dataset_key: str) -> str:
        if entity_type in (LinkEntityType.ROUTE, LinkEntityType.TRIP, LinkEntityType.STOP):
            if not re.fullmatch(r"[a-z0-9_]+", dataset_key):
                raise ValueError(f"dataset GTFS non valido: {dataset_key!r}")
            return f"gtfs:{dataset_key}:{entity_type.value}:{entity_id}"
        if entity_type is LinkEntityType.OSM_WAY:
            return f"osm:way:{entity_id}"
        return f"osm:poi:{entity_id}"

    @staticmethod
    def _link_ref(link: DisruptionLinkInput, entity_key: str | None, raw_reference: str) -> str:
        return "|".join(
            [
                entity_key or f"raw:{link.dataset_key or ''}:{raw_reference}",
                link.direction.value if link.direction else "",
                link.mode or "",
                link.from_stop_id or "",
                link.to_stop_id or "",
                str(link.from_stop_sequence) if link.from_stop_sequence is not None else "",
                str(link.to_stop_sequence) if link.to_stop_sequence is not None else "",
                link.service_date.isoformat() if link.service_date else "",
            ]
        )

    def _reference(self, entity_key: str) -> dict[str, Any] | None:
        rows = self._fetchall(
            """
            SELECT entity_key, domain, entity_type, dataset_key, entity_id,
                   service_id, display_name, mode, dataset_version, is_current
            FROM reference_entities
            WHERE entity_key = %s
            """,
            (entity_key,),
        )
        return rows[0] if rows else None

    def _service_active(self, trip_id: str, service_date: date, dataset_key: str) -> bool | None:
        datasets = self._fetchall(
            "SELECT gtfs_schema FROM gtfs_datasets WHERE dataset_key = %s AND is_active",
            (dataset_key,),
        )
        if not datasets:
            return None
        schema = datasets[0]["gtfs_schema"]
        if not isinstance(schema, str) or not _SCHEMA_RE.fullmatch(schema):
            raise ValueError(f"schema GTFS non valido: {schema!r}")
        rows = self._fetchall(
            f"""
            SELECT EXISTS (
                SELECT 1
                FROM "{schema}".trips t
                JOIN "{schema}".service_days sd
                  ON sd.service_id = t.service_id
                WHERE t.trip_id = %s AND sd.date = %s
            ) AS active
            """,
            (trip_id, service_date),
        )
        if not rows:
            return None
        return bool(rows[0]["active"])

    def _resolve_link(self, link: DisruptionLinkInput) -> dict[str, Any]:
        default_key = (
            self._gtfs_dataset_key
            if link.entity_type in (LinkEntityType.ROUTE, LinkEntityType.TRIP, LinkEntityType.STOP)
            else self._osm_dataset_key
        )
        dataset_key = link.dataset_key or default_key
        entity_key = self._entity_key(link.entity_type, link.entity_id, dataset_key)
        ref = self._reference(entity_key)
        raw_reference = link.raw_reference or f"{link.entity_type.value}:{link.entity_id}"
        dataset_version = link.dataset_version or (ref["dataset_version"] if ref else None)
        mode = link.mode or (ref.get("mode") if ref else None)
        service_active: bool | None = None
        note: str | None = None
        if ref is None:
            status = ResolutionStatus.UNRESOLVED
            entity_key_value = None
            note = "reference_not_found"
        elif not ref["is_current"]:
            status = ResolutionStatus.HISTORICAL
            entity_key_value = entity_key
            note = "reference_not_current"
        else:
            status = ResolutionStatus.RESOLVED
            entity_key_value = entity_key
        if (
            link.entity_type is LinkEntityType.TRIP
            and link.service_date is not None
            and ref is not None
            and ref.get("service_id")
        ):
            service_active = self._service_active(link.entity_id, link.service_date, dataset_key)
            if service_active is False:
                note = "; ".join(filter(None, [note, "service_not_active_on_date"]))
        return {
            "link_ref": self._link_ref(
                link.model_copy(update={"dataset_key": dataset_key}),
                entity_key_value,
                raw_reference,
            ),
            "entity_type": link.entity_type.value,
            "entity_key": entity_key_value,
            "raw_reference": raw_reference,
            "resolution_status": status.value,
            "resolution_note": note,
            "dataset_key": dataset_key,
            "dataset_version": dataset_version,
            "direction": link.direction.value if link.direction else None,
            "mode": mode,
            "from_stop_id": link.from_stop_id,
            "to_stop_id": link.to_stop_id,
            "from_stop_sequence": link.from_stop_sequence,
            "to_stop_sequence": link.to_stop_sequence,
            "service_date": link.service_date,
            "service_active": service_active,
            "details": link.details,
        }

    def upsert(self, disruption: DisruptionInput) -> DisruptionRecord:
        """Insert or update by (source_id, alert_id), preserving history."""
        incoming_hash = disruption.content_hash()
        cur = self._conn.cursor()
        try:
            cur.execute(
                """
                SELECT revision, content_hash
                FROM service_alerts
                WHERE source_id = %s AND alert_id = %s
                FOR UPDATE
                """,
                (disruption.source_id, disruption.alert_id),
            )
            existing = cur.fetchone()
            if existing is None:
                revision = 1
                changed = True
            else:
                old_revision, old_hash = existing
                changed = old_hash != incoming_hash
                revision = int(old_revision) + 1 if changed else int(old_revision)

            now = disruption.ingested_at or datetime.now(timezone.utc)
            resolved_at = now if disruption.lifecycle_status is LifecycleStatus.RESOLVED else None
            cancelled_at = now if disruption.lifecycle_status is LifecycleStatus.CANCELLED else None
            cur.execute(
                """
                INSERT INTO service_alerts (
                    route_id, stop_id, alert_id, severity, valid_from, valid_to,
                    source_id, confidence, title, body, zone_id, is_simulated,
                    data_reference, ingested_at, alert_type, effect, source_url,
                    content_hash, published_at, observed_at, timezone,
                    lifecycle_status, verification_status, uncertainty,
                    next_review_at, recurrence, revision, resolved_at,
                    cancelled_at, updated_at
                )
                VALUES (
                    NULL, NULL, %s, %s, %s, %s, %s, %s, %s, %s, NULL, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s::jsonb, %s, %s, %s, NOW()
                )
                ON CONFLICT (source_id, alert_id) DO UPDATE SET
                    severity = EXCLUDED.severity,
                    valid_from = EXCLUDED.valid_from,
                    valid_to = EXCLUDED.valid_to,
                    confidence = EXCLUDED.confidence,
                    title = EXCLUDED.title,
                    body = EXCLUDED.body,
                    is_simulated = EXCLUDED.is_simulated,
                    data_reference = EXCLUDED.data_reference,
                    ingested_at = EXCLUDED.ingested_at,
                    alert_type = EXCLUDED.alert_type,
                    effect = EXCLUDED.effect,
                    source_url = EXCLUDED.source_url,
                    content_hash = EXCLUDED.content_hash,
                    published_at = EXCLUDED.published_at,
                    observed_at = EXCLUDED.observed_at,
                    timezone = EXCLUDED.timezone,
                    lifecycle_status = EXCLUDED.lifecycle_status,
                    verification_status = EXCLUDED.verification_status,
                    uncertainty = EXCLUDED.uncertainty,
                    next_review_at = EXCLUDED.next_review_at,
                    recurrence = EXCLUDED.recurrence,
                    revision = EXCLUDED.revision,
                    resolved_at = EXCLUDED.resolved_at,
                    cancelled_at = EXCLUDED.cancelled_at,
                    updated_at = NOW()
                """,
                (
                    disruption.alert_id,
                    disruption.severity.value,
                    disruption.valid_from,
                    disruption.valid_to,
                    disruption.source_id,
                    float(disruption.confidence),
                    disruption.title,
                    disruption.description,
                    bool(disruption.is_simulated),
                    disruption.data_reference,
                    now,
                    disruption.alert_type,
                    disruption.effect.value,
                    disruption.source_url,
                    incoming_hash,
                    disruption.published_at,
                    disruption.observed_at,
                    disruption.timezone,
                    disruption.lifecycle_status.value,
                    disruption.verification_status.value,
                    disruption.uncertainty.value,
                    disruption.next_review_at,
                    json.dumps(disruption.recurrence.model_dump(mode="json"))
                    if disruption.recurrence
                    else None,
                    revision,
                    resolved_at,
                    cancelled_at,
                ),
            )
            if changed:
                cur.execute(
                    """
                    INSERT INTO service_alert_revisions (
                        source_id, alert_id, revision, content_hash, payload
                    )
                    VALUES (%s, %s, %s, %s, %s::jsonb)
                    ON CONFLICT (source_id, alert_id, revision) DO NOTHING
                    """,
                    (
                        disruption.source_id,
                        disruption.alert_id,
                        revision,
                        incoming_hash,
                        json.dumps(
                            disruption.model_dump(mode="json"),
                            ensure_ascii=False,
                            sort_keys=True,
                        ),
                    ),
                )

            cur.execute(
                """
                UPDATE service_alert_links
                SET is_current = FALSE, updated_at = NOW()
                WHERE source_id = %s AND alert_id = %s AND is_current
                """,
                (disruption.source_id, disruption.alert_id),
            )
            for link in disruption.links:
                resolved = self._resolve_link(link)
                cur.execute(
                    """
                    INSERT INTO service_alert_links (
                        source_id, alert_id, link_ref, entity_type, entity_key,
                        raw_reference, resolution_status, resolution_note,
                        dataset_key, dataset_version, direction, mode,
                        from_stop_id, to_stop_id, from_stop_sequence,
                        to_stop_sequence, service_date, service_active, details,
                        is_current, updated_at
                    )
                    VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s, %s::jsonb, TRUE, NOW()
                    )
                    ON CONFLICT (source_id, alert_id, link_ref) DO UPDATE SET
                        entity_type = EXCLUDED.entity_type,
                        entity_key = EXCLUDED.entity_key,
                        raw_reference = EXCLUDED.raw_reference,
                        resolution_status = EXCLUDED.resolution_status,
                        resolution_note = EXCLUDED.resolution_note,
                        dataset_key = EXCLUDED.dataset_key,
                        dataset_version = EXCLUDED.dataset_version,
                        direction = EXCLUDED.direction,
                        mode = EXCLUDED.mode,
                        from_stop_id = EXCLUDED.from_stop_id,
                        to_stop_id = EXCLUDED.to_stop_id,
                        from_stop_sequence = EXCLUDED.from_stop_sequence,
                        to_stop_sequence = EXCLUDED.to_stop_sequence,
                        service_date = EXCLUDED.service_date,
                        service_active = EXCLUDED.service_active,
                        details = EXCLUDED.details,
                        is_current = TRUE,
                        updated_at = NOW()
                    """,
                    (
                        disruption.source_id,
                        disruption.alert_id,
                        resolved["link_ref"],
                        resolved["entity_type"],
                        resolved["entity_key"],
                        resolved["raw_reference"],
                        resolved["resolution_status"],
                        resolved["resolution_note"],
                        resolved["dataset_key"],
                        resolved["dataset_version"],
                        resolved["direction"],
                        resolved["mode"],
                        resolved["from_stop_id"],
                        resolved["to_stop_id"],
                        resolved["from_stop_sequence"],
                        resolved["to_stop_sequence"],
                        resolved["service_date"],
                        resolved["service_active"],
                        json.dumps(resolved["details"], ensure_ascii=False),
                    ),
                )
            self._conn.commit()
        except Exception:
            self._conn.rollback()
            raise
        record = self.get(disruption.source_id, disruption.alert_id)
        assert record is not None
        return record

    def get(self, source_id: str, alert_id: str) -> DisruptionRecord | None:
        rows = self._fetchall(
            """
            SELECT source_id, alert_id, source_url, data_reference, title,
                   body AS description, alert_type, effect, severity, confidence,
                   published_at, observed_at, ingested_at, valid_from, valid_to,
                   timezone, lifecycle_status, verification_status, uncertainty,
                   is_simulated, next_review_at, recurrence, revision,
                   content_hash, resolved_at, cancelled_at, updated_at
            FROM service_alerts
            WHERE source_id = %s AND alert_id = %s
            """,
            (str(source_id), str(alert_id)),
        )
        if not rows:
            return None
        core = rows[0]
        links = self._fetchall(
            """
            SELECT l.link_ref, l.entity_type, l.entity_key,
                   r.entity_id AS entity_id, l.raw_reference,
                   l.resolution_status, l.resolution_note, l.dataset_key,
                   l.dataset_version, l.direction, l.mode, l.from_stop_id,
                   l.to_stop_id, l.from_stop_sequence, l.to_stop_sequence,
                   l.service_date, l.service_active, l.details, l.is_current,
                   r.is_current AS reference_is_current
            FROM service_alert_links l
            LEFT JOIN reference_entities r ON r.entity_key = l.entity_key
            WHERE l.source_id = %s AND l.alert_id = %s AND l.is_current
            ORDER BY l.link_id
            """,
            (str(source_id), str(alert_id)),
        )
        link_records: list[DisruptionLinkRecord] = []
        for link in links:
            status = link["resolution_status"]
            note = link["resolution_note"]
            if link["entity_key"] is not None:
                if link["reference_is_current"] is True:
                    status = ResolutionStatus.RESOLVED.value
                elif link["reference_is_current"] is False:
                    status = ResolutionStatus.HISTORICAL.value
                    note = note or "reference_not_current"
            link_records.append(
                DisruptionLinkRecord.model_validate(
                    {**link, "resolution_status": status, "resolution_note": note}
                )
            )
        return DisruptionRecord.model_validate(
            {
                **core,
                "links": [link.model_dump() for link in link_records],
            }
        )

    def set_lifecycle(
        self,
        source_id: str,
        alert_id: str,
        status: LifecycleStatus,
        *,
        at: datetime | None = None,
        note: str | None = None,
    ) -> DisruptionRecord:
        current = self.get(source_id, alert_id)
        if current is None:
            raise KeyError(f"disruption inesistente: {source_id}/{alert_id}")
        if current.lifecycle_status is status:
            return current
        now = at or datetime.now(timezone.utc)
        revision = current.revision + 1
        payload = {
            "source_id": source_id,
            "alert_id": alert_id,
            "lifecycle_status": status.value,
            "at": now.isoformat(),
            "note": note,
        }
        content_hash = hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        cur = self._conn.cursor()
        try:
            cur.execute(
                """
                UPDATE service_alerts
                SET lifecycle_status = %s,
                    resolved_at = CASE WHEN %s = 'resolved' THEN %s ELSE resolved_at END,
                    cancelled_at = CASE WHEN %s = 'cancelled' THEN %s ELSE cancelled_at END,
                    revision = %s,
                    content_hash = %s,
                    updated_at = NOW()
                WHERE source_id = %s AND alert_id = %s
                """,
                (
                    status.value,
                    status.value,
                    now,
                    status.value,
                    now,
                    revision,
                    content_hash,
                    str(source_id),
                    str(alert_id),
                ),
            )
            cur.execute(
                """
                INSERT INTO service_alert_revisions (
                    source_id, alert_id, revision, content_hash, payload
                )
                VALUES (%s, %s, %s, %s, %s::jsonb)
                ON CONFLICT (source_id, alert_id, revision) DO NOTHING
                """,
                (
                    str(source_id),
                    str(alert_id),
                    revision,
                    content_hash,
                    json.dumps(payload, ensure_ascii=False, sort_keys=True),
                ),
            )
            self._conn.commit()
        except Exception:
            self._conn.rollback()
            raise
        updated = self.get(source_id, alert_id)
        assert updated is not None
        return updated

    def resolve(
        self, source_id: str, alert_id: str, *, at: datetime | None = None, note: str | None = None
    ) -> DisruptionRecord:
        return self.set_lifecycle(source_id, alert_id, LifecycleStatus.RESOLVED, at=at, note=note)

    def cancel(
        self, source_id: str, alert_id: str, *, at: datetime | None = None, note: str | None = None
    ) -> DisruptionRecord:
        return self.set_lifecycle(source_id, alert_id, LifecycleStatus.CANCELLED, at=at, note=note)

    def list_relevant(
        self,
        start: datetime,
        end: datetime,
        *,
        include_simulated: bool = False,
    ) -> list[DisruptionRecord]:
        """Return lifecycle-active alerts whose validity overlaps a window.

        Recurrence is evaluated in Python by ``is_applicable_at``; this method
        only narrows the database rows, keeping the query bounded.
        """
        if start.tzinfo is None or end.tzinfo is None:
            raise ValueError("start/end devono essere timezone-aware")
        if end < start:
            raise ValueError("end non può precedere start")
        rows = self._fetchall(
            """
            SELECT DISTINCT a.source_id, a.alert_id
            FROM service_alerts a
            WHERE a.lifecycle_status = 'active'
              AND a.published_at <= %s
              AND a.valid_from <= %s
              AND (a.valid_to IS NULL OR a.valid_to >= %s)
              AND (%s OR NOT a.is_simulated)
              AND EXISTS (
                  SELECT 1 FROM service_alert_links l
                  WHERE l.source_id = a.source_id AND l.alert_id = a.alert_id
                    AND l.is_current
                    AND l.resolution_status IN ('resolved','unresolved','historical')
              )
            ORDER BY a.source_id, a.alert_id
            """,
            (end, end, start, include_simulated),
        )
        records: list[DisruptionRecord] = []
        for row in rows:
            record = self.get(row["source_id"], row["alert_id"])
            if record is not None:
                records.append(record)
        return records

    def expire_due(self, now: datetime) -> list[DisruptionRecord]:
        """Close active alerts whose explicit valid_to has passed."""
        rows = self._fetchall(
            """
            SELECT source_id, alert_id
            FROM service_alerts
            WHERE lifecycle_status = 'active'
              AND valid_to IS NOT NULL AND valid_to < %s
            ORDER BY source_id, alert_id
            """,
            (now,),
        )
        return [
            self.set_lifecycle(
                row["source_id"],
                row["alert_id"],
                LifecycleStatus.EXPIRED,
                at=now,
                note="valid_to superato",
            )
            for row in rows
        ]

    def expire_stale_unknown(self, now: datetime) -> list[DisruptionRecord]:
        """Close unverified alerts whose unknown end reached its review TTL."""
        rows = self._fetchall(
            """
            SELECT source_id, alert_id
            FROM service_alerts
            WHERE lifecycle_status = 'active'
              AND valid_to IS NULL
              AND next_review_at IS NOT NULL AND next_review_at < %s
              AND verification_status <> 'verified'
            ORDER BY source_id, alert_id
            """,
            (now,),
        )
        return [
            self.set_lifecycle(
                row["source_id"],
                row["alert_id"],
                LifecycleStatus.EXPIRED,
                at=now,
                note="scadenza ignota: revisione non effettuata",
            )
            for row in rows
        ]

    def find_applicable(
        self,
        entity_type: LinkEntityType,
        entity_id: str,
        at: datetime,
        *,
        dataset_key: str | None = None,
        service_date: date | None = None,
        direction: Direction | None = None,
        mode: str | None = None,
        include_simulated: bool = False,
    ) -> list[DisruptionRecord]:
        """Return active disruptions for an exact entity and time window.

        Simulated fixtures are excluded by default. A real journey must never
        be changed by a demo row merely because it exists in the same table.
        """
        if at.tzinfo is None or at.utcoffset() is None:
            raise ValueError("at deve essere timezone-aware")
        default_key = (
            self._gtfs_dataset_key
            if entity_type in (LinkEntityType.ROUTE, LinkEntityType.TRIP, LinkEntityType.STOP)
            else self._osm_dataset_key
        )
        entity_key = self._entity_key(entity_type, entity_id, dataset_key or default_key)
        direction_value = direction.value if direction else None
        rows = self._fetchall(
            """
            SELECT DISTINCT a.source_id, a.alert_id
            FROM service_alerts a
            JOIN service_alert_links l
              ON l.source_id = a.source_id AND l.alert_id = a.alert_id
            WHERE l.is_current
              AND l.resolution_status = 'resolved'
              AND l.entity_key = %s
              AND a.lifecycle_status = 'active'
              AND a.published_at <= %s
              AND a.valid_from <= %s
              AND (a.valid_to IS NULL OR a.valid_to >= %s)
              AND (
                  l.direction IS NULL OR l.direction = 'both'
                  OR %s::text IS NULL OR l.direction = %s::text
              )
              AND (
                  l.mode IS NULL OR %s::text IS NULL OR l.mode = %s::text
              )
              AND (l.service_date IS NULL OR l.service_date = %s)
              AND (l.service_active IS NOT FALSE)
              AND (%s OR NOT a.is_simulated)
            ORDER BY a.source_id, a.alert_id
            """,
            (
                entity_key,
                at,
                at,
                at,
                direction_value,
                direction_value,
                mode,
                mode,
                service_date,
                include_simulated,
            ),
        )
        records: list[DisruptionRecord] = []
        for row in rows:
            record = self.get(row["source_id"], row["alert_id"])
            if record is not None and record.is_applicable_at(at, service_date=service_date):
                records.append(record)
        return records
