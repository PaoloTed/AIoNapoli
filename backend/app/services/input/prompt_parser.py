"""Deterministic Italian prompt parser used when the model is unavailable.

It is intentionally explicit: unknown or contradictory requests produce
clarification/contradiction instead of guessed dates or places.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from shared.schemas.journeys import JourneyPreferences

_WEEKDAYS = {
    "lunedi": 0,
    "lunedì": 0,
    "martedi": 1,
    "martedì": 1,
    "mercoledi": 2,
    "mercoledì": 2,
    "giovedi": 3,
    "giovedì": 3,
    "venerdi": 4,
    "venerdì": 4,
    "sabato": 5,
    "domenica": 6,
}
_TIME_RE = re.compile(
    r"\b(alle|entro|per\s+le|verso\s+le|ore)\s+(?:le\s+)?"
    r"(\d{1,2})(?:[:.](\d{2}))?\b",
    re.IGNORECASE,
)
_DATE_NUMERIC_RE = re.compile(r"\b(\d{1,2})[/-](\d{1,2})(?:[/-](\d{2,4}))?\b")
_ISO_DATE_RE = re.compile(r"\b(20\d{2})-(\d{2})-(\d{2})\b")
_RELATIVE_RE = re.compile(
    r"\btra\s+(un|una|mezz)?\s*(?:'|’)?\s*(ora|ore|minut[oi])\b", re.IGNORECASE
)
_RELATIVE_NUM_RE = re.compile(r"\btra\s+(\d+)\s*(minut[oi]|or[ae])\b", re.IGNORECASE)
_PREFERENCE_MARKERS = [
    "con meno cammino possibile",
    "con meno cammino",
    "meno cammino possibile",
    "meno cammino",
    "poco cammino",
    "meno a piedi",
    "con meno cambi",
    "meno cambi",
    "pochi cambi",
    "senza salite",
    "senza scale",
    "accessibile",
    "in sedia a rotelle",
    "con ascensore",
    "possibilmente",
    "preferibilmente",
]


@dataclass
class PromptParseResult:
    origin_text: str | None = None
    destination_text: str | None = None
    depart_at: datetime | None = None
    arrive_by: datetime | None = None
    explicit_depart: bool = False
    explicit_arrive: bool = False
    preferences: JourneyPreferences = field(default_factory=JourneyPreferences)
    transit_only: bool = False
    contradictions: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _strip_preferences(text: str) -> str:
    cleaned = text
    for marker in _PREFERENCE_MARKERS:
        cleaned = re.sub(re.escape(marker), " ", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(
        r"\b(?:con|preferibilmente|possibilmente)\s+(?:il\s+)?(?:minor|minore)\s+"
        r"(?:cammino|cambi)\b",
        " ",
        cleaned,
        flags=re.IGNORECASE,
    )
    return re.sub(r"\s+", " ", cleaned).strip(" ,.;")


def _extract_places(prompt: str) -> tuple[str | None, str | None]:
    text = _strip_preferences(prompt)
    # Remove time clauses from the place text, without removing place names.
    text = re.sub(
        r"\b(?:oggi|domani|dopodomani|stasera|stamattina|adesso|subito)\b",
        " ",
        text,
        flags=re.IGNORECASE,
    )
    text = _TIME_RE.sub(" ", text)
    text = _RELATIVE_NUM_RE.sub(" ", text)
    text = _RELATIVE_RE.sub(" ", text)
    text = _DATE_NUMERIC_RE.sub(" ", text)
    text = _ISO_DATE_RE.sub(" ", text)
    text = re.sub(
        r"[,;]?\s*(?:e\s+)?(?:devo|voglio|vorrei|desidero)\s+"
        r"(?:arrivare|partire|essere)\b.*$",
        "",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(
        r"[,;]?\s*(?:per\s+)?arrivare\s+(?:entro|per\s+le|alle)\b.*$",
        "",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(
        r"\b(?:lunedi|lunedì|martedi|martedì|mercoledi|mercoledì|giovedi|giovedì|"
        r"venerdi|venerdì|sabato|domenica)\b",
        " ",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(r"\s+", " ", text).strip(" ,.;")

    patterns = [
        (r"^(?:come\s+)?(?:arrivo|giungo)\s+(?:a|in|presso)\s+(.+?)\s+da\s+(.+)$", "reverse"),
        (
            r"^(?:parto|partire|partenza)\s+da\s+(.+?)\s+(?:a|ad|verso|fino\s+a|per)\s+(.+)$",
            "normal",
        ),
        (r"^dalla\s+(.+?)\s+alla\s+(.+)$", "normal"),
        (r"^dalla\s+(.+?)\s+al\s+(.+)$", "normal"),
        (r"^dal\s+(.+?)\s+alla\s+(.+)$", "normal"),
        (r"^dal\s+(.+?)\s+al\s+(.+)$", "normal"),
        (r"^da\s+qui\s+(?:a|ad|verso|fino\s+a|per)\s+(.+)$", "from_here"),
        (r"^da\s+(.+?)\s+alla\s+(.+)$", "normal"),
        (r"^da\s+(.+?)\s+al\s+(.+)$", "normal"),
        (r"^da\s+(.+?)\s+(?:a|ad|verso|fino\s+a|per)\s+(.+)$", "normal"),
        (
            r"^(?:devo\s+andare|voglio\s+andare|andare)\s+da\s+(.+?)\s+(?:a|verso|fino\s+a)\s+(.+)$",
            "normal",
        ),
        (r"^(?:portami|vai|andiamo)\s+(?:a|in|verso)\s+(.+)$", "destination_only"),
    ]
    for pattern, kind in patterns:
        match = re.match(pattern, text, flags=re.IGNORECASE)
        if not match:
            continue
        if kind == "reverse":
            destination, origin = match.group(1), match.group(2)
        elif kind == "from_here":
            origin, destination = "qui", match.group(1)
        elif kind == "destination_only":
            origin, destination = None, match.group(1)
        else:
            origin, destination = match.group(1), match.group(2)
        return (
            _clean_place(origin) if origin else None,
            _clean_place(destination) if destination else None,
        )
    return None, None


def _clean_place(value: str) -> str:
    text = value.strip(" ,.;:-")
    text = re.sub(
        r"^(?:partendo\s+da|a partire\s+da|arrivando\s+a|fino\s+a)\s+",
        "",
        text,
        flags=re.IGNORECASE,
    )
    return text.strip()


def _resolve_date(prompt: str, now: datetime) -> tuple[datetime.date, str | None]:
    lower = prompt.casefold()
    day = now.date()
    if "dopodomani" in lower:
        return day + timedelta(days=2), "dopodomani"
    if "domani" in lower:
        return day + timedelta(days=1), "domani"
    if "oggi" in lower or "stasera" in lower or "stamattina" in lower:
        return day, "oggi"
    iso = _ISO_DATE_RE.search(prompt)
    if iso:
        try:
            return datetime(int(iso.group(1)), int(iso.group(2)), int(iso.group(3))).date(), "iso"
        except ValueError:
            return day, "invalid"
    numeric = _DATE_NUMERIC_RE.search(prompt)
    if numeric:
        day_value = int(numeric.group(1))
        month_value = int(numeric.group(2))
        year_value = int(numeric.group(3) or now.year)
        if year_value < 100:
            year_value += 2000
        try:
            return datetime(year_value, month_value, day_value).date(), "numeric"
        except ValueError:
            return day, "invalid"
    for name, weekday in _WEEKDAYS.items():
        if re.search(rf"\b{re.escape(name)}\b", lower):
            delta = (weekday - now.weekday()) % 7
            if delta == 0:
                delta = 7
            return day + timedelta(days=delta), name
    return day, None


def _resolve_time_phrase(
    prompt: str, now: datetime, timezone: ZoneInfo
) -> tuple[datetime | None, datetime | None, bool, bool, list[str]]:
    lower = prompt.casefold()
    warnings: list[str] = []
    relative_num = _RELATIVE_NUM_RE.search(lower)
    if relative_num:
        quantity = int(relative_num.group(1))
        unit = relative_num.group(2)
        delta = timedelta(hours=quantity) if unit.startswith("or") else timedelta(minutes=quantity)
        return now + delta, None, True, False, warnings
    relative = _RELATIVE_RE.search(lower)
    if relative:
        quantity = 1
        if relative.group(1) in {"mezz", "mezza"}:
            quantity = 0.5
        unit = relative.group(2)
        delta = timedelta(hours=quantity) if unit.startswith("or") else timedelta(minutes=quantity)
        return now + delta, None, True, False, warnings
    if "adesso" in lower or "subito" in lower:
        return now, None, True, False, warnings
    if "stasera" in lower and not _TIME_RE.search(prompt):
        target = now.replace(hour=20, minute=0, second=0, microsecond=0)
    elif "stamattina" in lower and not _TIME_RE.search(prompt):
        target = now.replace(hour=8, minute=0, second=0, microsecond=0)
    elif any(
        marker in lower for marker in ("nel pomeriggio", "di pomeriggio")
    ) and not _TIME_RE.search(prompt):
        target = now.replace(hour=15, minute=0, second=0, microsecond=0)
    else:
        target = None

    matches = list(_TIME_RE.finditer(prompt))
    date_value, date_token = _resolve_date(prompt, now)
    if date_token == "invalid":
        warnings.append("data non valida: serve un chiarimento")
        return None, None, False, False, warnings
    depart_time: time | None = None
    arrive_time: time | None = None
    for match in matches:
        keyword = re.sub(r"\s+", " ", match.group(1).casefold())
        hour = int(match.group(2))
        minute = int(match.group(3) or 0)
        if hour > 23 or minute > 59:
            warnings.append(f"orario non valido: {match.group(0)}")
            continue
        value = time(hour, minute)
        if keyword in {"entro", "per le"}:
            arrive_time = value
        else:
            depart_time = value

    explicit_depart = depart_time is not None
    explicit_arrive = arrive_time is not None
    if target is not None and not matches:
        depart_time = target.time().replace(second=0, microsecond=0)
        explicit_depart = True
        warnings.append("orario non specificato: usata una fascia dichiarata")

    if depart_time is None and arrive_time is None:
        return None, None, False, False, warnings

    if date_token is None and depart_time is not None and arrive_time is not None:
        # Both phrases refer to the same day. Compare them on one base date so
        # a past time on one side cannot hide a real contradiction.
        base_date = date_value
        if depart_time <= now.time().replace(second=0, microsecond=0):
            base_date = date_value + timedelta(days=1)
            warnings.append("orario gia' passato: interpretato per il giorno successivo")
        depart = datetime.combine(base_date, depart_time, tzinfo=timezone)
        arrive = datetime.combine(base_date, arrive_time, tzinfo=timezone)
        return depart, arrive, True, True, warnings

    def _on_date(value: time) -> datetime:
        candidate = datetime.combine(date_value, value, tzinfo=timezone)
        if date_token is None and candidate <= now:
            candidate += timedelta(days=1)
            warnings.append("orario gia' passato: interpretato per il giorno successivo")
        return candidate

    depart = _on_date(depart_time) if depart_time is not None else None
    arrive = _on_date(arrive_time) if arrive_time is not None else None
    return depart, arrive, explicit_depart, explicit_arrive, warnings


def _preferences(prompt: str) -> tuple[JourneyPreferences, bool, list[str]]:
    lower = prompt.casefold()
    warnings: list[str] = []
    minimize_walk = any(
        token in lower
        for token in ("meno cammino", "poco cammino", "meno a piedi", "minimo cammino")
    )
    minimize_transfers = any(
        token in lower for token in ("meno cambi", "pochi cambi", "minimo cambi")
    )
    unsupported: list[str] = []
    for token, label in (
        ("senza salite", "assenza di salite"),
        ("senza scale", "assenza di scale"),
        ("accessibile", "accessibilita' verificata"),
        ("sedia a rotelle", "accessibilita' in sedia a rotelle"),
        ("ascensore", "ascensore disponibile"),
    ):
        if token in lower:
            unsupported.append(label)
    modes: list[str] = []
    if re.search(r"\b(solo\s+bus|in\s+bus|con\s+il\s+bus|autobus)\b", lower):
        modes.extend(["WALK", "BUS"])
    if re.search(r"\b(solo\s+metro|in\s+metro|con\s+la\s+metro|metropolitana)\b", lower):
        modes.extend(["WALK", "SUBWAY"])
    if re.search(r"\b(treno|ferrovia|ferroviario)\b", lower):
        modes.extend(["WALK", "RAIL"])
    if re.search(r"\b(tram)\b", lower):
        modes.extend(["WALK", "TRAM"])
    if re.search(r"\b(funicolare)\b", lower):
        modes.extend(["WALK", "FUNICULAR"])
    if "a piedi" in lower and not modes:
        unsupported.append("viaggio esclusivamente a piedi")
    modes = list(dict.fromkeys(modes)) or ["WALK", "BUS", "RAIL", "SUBWAY"]
    transit_only = any(
        token in lower for token in ("senza camminare", "solo mezzi", "solo trasporto pubblico")
    )
    return (
        JourneyPreferences(
            minimize_walk=minimize_walk,
            minimize_transfers=minimize_transfers,
            modes=modes,
            unsupported_constraints=unsupported,
        ),
        transit_only,
        warnings,
    )


def parse_prompt(
    prompt: str,
    *,
    now: datetime,
    timezone: ZoneInfo,
) -> PromptParseResult:
    origin, destination = _extract_places(prompt)
    depart, arrive, explicit_depart, explicit_arrive, warnings = _resolve_time_phrase(
        prompt, now, timezone
    )
    preferences, transit_only, pref_warnings = _preferences(prompt)
    warnings.extend(pref_warnings)
    contradictions: list[str] = []
    if depart is not None and arrive is not None and arrive <= depart:
        contradictions.append("l'arrivo richiesto non puo' precedere o coincidere con la partenza")
    if not explicit_depart and not explicit_arrive:
        depart = now
        warnings.append("partenza non specificata: usata l'ora corrente Europe/Rome")
    missing = []
    if not origin:
        missing.append("origin")
    if not destination:
        missing.append("destination")
    if (explicit_depart or explicit_arrive) is False and not depart:
        missing.append("time")
    return PromptParseResult(
        origin_text=origin,
        destination_text=destination,
        depart_at=depart,
        arrive_by=arrive,
        explicit_depart=explicit_depart,
        explicit_arrive=explicit_arrive,
        preferences=preferences,
        transit_only=transit_only,
        contradictions=contradictions,
        missing=missing,
        warnings=warnings,
    )


__all__ = ["PromptParseResult", "parse_prompt"]
