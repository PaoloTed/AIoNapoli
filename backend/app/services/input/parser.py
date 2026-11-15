"""Natural language trip request parser with regex fallback (05_agente_input.md §4-5)."""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any

from app.domain.models.trip_request import (
    ParsedLocation,
    ParsedRequest,
    TripLocation,
    TripRequest,
)
from app.services.input.geocoder import Geocoder


class RequestParser:
    """Parses natural language mobility queries into structured TripRequest objects."""

    def __init__(self, geocoder: Geocoder | None = None) -> None:
        self.geocoder = geocoder or Geocoder()

    def parse_request(
        self,
        text: str,
        now: datetime | None = None,
    ) -> tuple[TripRequest | None, ParsedRequest, list[dict[str, str]], str | None]:
        """Parse text into (TripRequest | None, ParsedRequest, unresolved_list, question)."""
        ref_now = now or datetime.now(timezone.utc)
        if ref_now.tzinfo is None:
            ref_now = ref_now.replace(tzinfo=timezone.utc)

        raw = text.strip()
        origin_text: str | None = None
        dest_text: str | None = None

        # 1. Regex Pattern for Origin -> Destination
        # e.g. "portami da Bagnoli al MANN..." or "da Fuorigrotta a Toledo..."
        m_da_a = re.search(
            r"(?:portami\s+)?da\s+(.+?)\s+(?:a|al|alla|allo|agli|alle|all'|in|verso)\s+(.+?)(?:\s+(?:domani|oggi|stasera|alle|ore|senza)|$)",
            raw,
            re.IGNORECASE,
        )
        if m_da_a:
            origin_text = m_da_a.group(1).strip()
            dest_text = m_da_a.group(2).strip()
        else:
            # "come arrivo a/in/al MANN..."
            m_arrive = re.search(
                r"come\s+arrivo\s+(?:a|al|alla|allo|in|verso)\s+(.+?)(?:\s+(?:domani|oggi|stasera|alle|ore|dalle|senza)|$)",
                raw,
                re.IGNORECASE,
            )
            if m_arrive:
                dest_text = m_arrive.group(1).strip()
                # Default origin
                origin_text = "Bagnoli"
            else:
                # Direct coord arrow: "coord -> coord"
                parts = re.split(r"\s*(?:->|=>|a)\s*", raw, maxsplit=1)
                if len(parts) == 2:
                    origin_text = parts[0].strip()
                    dest_text = parts[1].strip()

        # 2. Extract when
        when_dt = ref_now
        when_was_rel = False
        when_src: str | None = None

        if "domani" in raw.lower():
            when_dt = when_dt + timedelta(days=1)
            when_was_rel = True
            when_src = "domani"
        elif "stasera" in raw.lower():
            when_dt = when_dt.replace(hour=20, minute=0, second=0, microsecond=0)
            when_was_rel = True
            when_src = "stasera"
        elif "tra un'ora" in raw.lower() or "tra 1 ora" in raw.lower():
            when_dt = when_dt + timedelta(hours=1)
            when_was_rel = True
            when_src = "tra un'ora"

        m_hour = re.search(r"(?:alle|dalle|ore)\s+(\d{1,2})(?::(\d{2}))?", raw, re.IGNORECASE)
        if m_hour:
            h = int(m_hour.group(1))
            m = int(m_hour.group(2)) if m_hour.group(2) else 0
            if 0 <= h <= 23 and 0 <= m <= 59:
                when_dt = when_dt.replace(hour=h, minute=m, second=0, microsecond=0)
                when_src = f"ore {h}:{m:02d}"

        # 3. Extract constraints
        constraints: dict[str, Any] = {}
        if re.search(r"senza\s+(?:troppi\s+)?cambi", raw, re.IGNORECASE):
            constraints["max_transfers"] = 1

        parsed_origin = (
            ParsedLocation(raw_text=origin_text or "", kind_guess="zone") if origin_text else None
        )
        parsed_dest = (
            ParsedLocation(raw_text=dest_text or "", kind_guess="poi") if dest_text else None
        )

        parsed_req = ParsedRequest(
            origin=parsed_origin,
            destination=parsed_dest,
            when_iso=when_dt,
            when_was_relative=when_was_rel,
            when_source_text=when_src,
            constraints=constraints,
            unresolved_hints=(),
            parser_confidence=0.90 if (origin_text and dest_text) else 0.40,
        )

        # 4. Resolve via Geocoder
        unresolved: list[dict[str, str]] = []
        loc_origin: TripLocation | None = None
        loc_dest: TripLocation | None = None

        if origin_text:
            loc_origin = self.geocoder.resolve(origin_text)
            if not loc_origin:
                unresolved.append(
                    {
                        "field": "origin",
                        "raw_text": origin_text,
                        "reason": "Luogo di origine non risolto a Napoli",
                    }
                )
        else:
            unresolved.append(
                {"field": "origin", "raw_text": "", "reason": "Origine non specificata"}
            )

        if dest_text:
            loc_dest = self.geocoder.resolve(dest_text)
            if not loc_dest:
                unresolved.append(
                    {
                        "field": "destination",
                        "raw_text": dest_text,
                        "reason": "Luogo di destinazione non risolto a Napoli",
                    }
                )
        else:
            unresolved.append(
                {"field": "destination", "raw_text": "", "reason": "Destinazione non specificata"}
            )

        question: str | None = None
        if unresolved:
            missing_fields = [u["field"] for u in unresolved]
            if "destination" in missing_fields:
                question = "Quale luogo intendi per la destinazione?"
            elif "origin" in missing_fields:
                question = "Da dove desideri partire?"

            return None, parsed_req, unresolved, question

        assert loc_origin is not None and loc_dest is not None

        trip_req = TripRequest(
            origin=loc_origin,
            destination=loc_dest,
            when=when_dt,
            constraints=constraints,
        )
        return trip_req, parsed_req, [], None
