"""Deterministic pre-filter before spending model tokens.

Relevance here only decides whether a document is worth semantic reading. It
never decides that a news item is an obstacle: effect and lifecycle are set by
the validated extraction contract.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from app.config.sources import SourceDefinition
from app.services.ingestion.parsing import ParsedEntry

MOBILITY_TERMS = {
    "traffico",
    "viabilita",
    "circolazione",
    "chiusura",
    "chiuso",
    "riapertura",
    "ripristino",
    "deviazione",
    "limitazione",
    "interruzione",
    "sospensione",
    "soppressione",
    "cancellazione",
    "ritardo",
    "sciopero",
    "allerta",
    "meteo",
    "maltempo",
    "incidente",
    "cantiere",
    "lavori",
    "manifestazione",
    "accessibilita",
    "ascensore",
    "ascensori",
    "scala mobile",
    "funicolare",
    "metro",
    "metropolitana",
    "autobus",
    "bus",
    "tram",
    "treno",
    "ferrovia",
    "ferroviaria",
    "linea",
    "fermata",
    "stazione",
    "aeroporto",
    "porto",
    "traghetto",
    "crociera",
    "crociere",
    "tangenziale",
    "autostrada",
    "esodo",
    "traffico intenso",
    "code",
    "mobilita",
}

OBSTACLE_TERMS = {
    "chiusur",
    "interruzion",
    "sospension",
    "cancellazion",
    "soppress",
    "deviazion",
    "limitazion",
    "divieto",
    "sciopero",
    "allerta",
    "incidente",
    "cantiere",
    "lavori",
    "guasto",
    "avaria",
    "blackout",
    "dissesto",
    "cedimento",
    "smottamento",
    "allagamento",
    "esondazione",
    "mareggiata",
    "frana",
    "terremoto",
    "sisma",
    "bradisisma",
    "eruzione",
    "cenere",
    "dirottamento",
    "collisione",
}

WEATHER_TERMS = {
    "allerta",
    "avviso",
    "bollettino",
    "criticita",
    "idrogeolog",
    "idraulica",
    "temporale",
    "vento",
    "mareggiata",
    "caldo",
    "pioggia",
}

LOCAL_TERMS = {
    "napoli",
    "napoletano",
    "napoletana",
    "campania",
    "campano",
    "chiaiano",
    "bagnoli",
    "fuorigrotta",
    "vomero",
    "chiaia",
    "municipio",
    "posillipo",
    "piazza garibaldi",
    "garibaldi",
    "capodichino",
    "capodimonte",
    "ischia",
    "procida",
    "capri",
    "sorrento",
    "pompei",
    "ercolano",
    "torre annunziata",
    "torre del greco",
    "salerno",
    "caserta",
    "pozzuoli",
    "campi flegrei",
    "flegrea",
    "flegreo",
    "vesuvio",
    "vesuviano",
    "aversa",
    "afragola",
    "giugliano",
    "frattamaggiore",
    "castellammare",
    "nola",
    "avellino",
    "benevento",
    "a1",
    "a2",
    "a3",
    "a16",
    "a30",
    "a56",
    "tangenziale di napoli",
    "area metropolitana",
}

CULTURE_TERMS = {
    "museo",
    "mostra",
    "sito archeologico",
    "parco archeologico",
    "reggia",
    "capodimonte",
    "ercolano",
    "pompei",
    "vesuvio",
    "citta della scienza",
    "mostra d oltremare",
    "teatro",
    "concerto",
    "evento",
    "manifestazione",
    "visita",
    "apertura",
    "chiusura",
    "accessibilita",
}

SEISMIC_RE = re.compile(r"(?:magnitudo|magnitude|ml|md|mw)\s*[:=]?\s*(\d+(?:[.,]\d+)?)", re.I)


def _normalize(text: str) -> str:
    value = unicodedata.normalize("NFKD", text.casefold())
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = value.replace("à", "a").replace("è", "e").replace("é", "e")
    value = value.replace("ì", "i").replace("ò", "o").replace("ù", "u")
    value = re.sub(r"\s+", " ", value)
    return value


def _has_any(text: str, terms: set[str]) -> list[str]:
    return sorted(term for term in terms if term in text)


@dataclass(frozen=True)
class RelevanceDecision:
    candidate: bool
    reason: str
    matched: list[str]
    local: bool
    filter_version: str
    is_obstacle_candidate: bool

    def to_output(self) -> dict[str, object]:
        return {
            "candidate": self.candidate,
            "reason": self.reason,
            "matched": self.matched,
            "local": self.local,
            "filter_version": self.filter_version,
            "is_obstacle_candidate": self.is_obstacle_candidate,
        }


def assess_relevance(
    entry: ParsedEntry,
    source: SourceDefinition,
    *,
    filter_version: str = "1",
) -> RelevanceDecision:
    """Return a conservative, auditable gate for the LLM extraction step."""
    title = _normalize(entry.title)
    body = _normalize(entry.body[:12000])
    text = f"{title} {body}"
    mobility = _has_any(text, MOBILITY_TERMS)
    obstacle = _has_any(text, OBSTACLE_TERMS)
    local = bool(_has_any(text, LOCAL_TERMS))
    weather = _has_any(text, WEATHER_TERMS)
    culture = _has_any(text, CULTURE_TERMS)

    if source.kind == "non_rss":
        return RelevanceDecision(False, "fonte_non_rss", [], local, filter_version, False)

    if source.source_class == "aggregator":
        if local and mobility:
            return RelevanceDecision(
                True,
                "aggregatore_locale_con_parola_mobilita",
                sorted(set(mobility + obstacle))[:20],
                local,
                filter_version,
                bool(obstacle),
            )
        return RelevanceDecision(
            False, "aggregatore_senza_rilevanza_locale", [], local, filter_version, False
        )

    if source.source_class == "local_news":
        if source.local_relevance == "required" and not local:
            return RelevanceDecision(
                False, "news_senza_riferimento_locale", [], local, filter_version, False
            )
        if mobility or obstacle:
            return RelevanceDecision(
                True,
                "news_locale_con_parola_mobilita" if local else "news_con_parola_mobilita",
                sorted(set(mobility + obstacle))[:20],
                local,
                filter_version,
                bool(obstacle),
            )
        return RelevanceDecision(
            False, "news_senza_parola_mobilita", [], local, filter_version, False
        )

    if source.source_class == "tourism_culture":
        site_match = source.operator and _normalize(source.operator.replace("_", " ")) in text
        if source.local_relevance == "required" and not local and not site_match:
            return RelevanceDecision(
                False, "cultura_senza_riferimento_locale", [], local, filter_version, False
            )
        if culture and (obstacle or mobility):
            return RelevanceDecision(
                True,
                "cultura_con_impatto_potenziale",
                sorted(set(culture + obstacle + mobility))[:20],
                local,
                filter_version,
                bool(obstacle),
            )
        if culture:
            return RelevanceDecision(
                True,
                "evento_culturale_da_valutare",
                sorted(set(culture))[:20],
                local,
                filter_version,
                False,
            )
        return RelevanceDecision(
            False, "cultura_senza_impatto_mobilita", [], local, filter_version, False
        )

    if source.source_class == "civil_protection":
        if weather and (obstacle or "bollettino" in text or "avviso" in text):
            if source.local_relevance == "required" and not local:
                return RelevanceDecision(
                    False,
                    "protezione_civile_senza_riferimento_locale",
                    [],
                    local,
                    filter_version,
                    False,
                )
            return RelevanceDecision(
                True,
                "protezione_civile_allerta_o_bollettino",
                sorted(set(weather + obstacle))[:20],
                local,
                filter_version,
                bool(obstacle),
            )
        return RelevanceDecision(
            False, "protezione_civile_senza_allerta", [], local, filter_version, False
        )

    if source.source_class == "national_context":
        if source.operator == "ingv":
            match = SEISMIC_RE.search(text)
            magnitude = float(match.group(1).replace(",", ".")) if match else None
            if local and (magnitude is None or magnitude >= 1.5):
                return RelevanceDecision(
                    True,
                    "sisma_locale",
                    [f"magnitudo={magnitude}"] if magnitude is not None else ["sisma_locale"],
                    local,
                    filter_version,
                    True,
                )
            return RelevanceDecision(
                False, "sisma_non_locale_o_sotto_soglia", [], local, filter_version, False
            )
        if source.local_relevance == "required" and not local:
            return RelevanceDecision(
                False, "fonte_nazionale_senza_riferimento_locale", [], local, filter_version, False
            )
        if mobility or obstacle or weather:
            return RelevanceDecision(
                True,
                "fonte_nazionale_pertinente_al_territorio",
                sorted(set(mobility + obstacle + weather))[:20],
                local,
                filter_version,
                bool(obstacle),
            )
        return RelevanceDecision(
            False, "fonte_nazionale_senza_parola_mobilita", [], local, filter_version, False
        )

    if source.source_class == "local_government":
        if mobility or obstacle or weather:
            return RelevanceDecision(
                True,
                "ente_locale_con_parola_mobilita",
                sorted(set(mobility + obstacle + weather))[:20],
                local,
                filter_version,
                bool(obstacle),
            )
        return RelevanceDecision(
            False, "ente_locale_senza_parola_mobilita", [], local, filter_version, False
        )

    if source.source_class == "official_transport":
        if source.operator == "mit":
            if local and (mobility or obstacle):
                return RelevanceDecision(
                    True,
                    "sciopero_nazionale_con_ricaduta_locale",
                    sorted(set(mobility + obstacle))[:20],
                    local,
                    filter_version,
                    True,
                )
            return RelevanceDecision(
                False, "sciopero_senza_ricaduta_locale", [], local, filter_version, False
            )
        if source.operator == "cciss":
            if local and (mobility or obstacle):
                return RelevanceDecision(
                    True,
                    "traffico_nazionale_con_riferimento_locale",
                    sorted(set(mobility + obstacle))[:20],
                    local,
                    filter_version,
                    True,
                )
            return RelevanceDecision(
                False, "traffico_senza_riferimento_locale", [], local, filter_version, False
            )
        if source.local_relevance == "required" and not local:
            return RelevanceDecision(
                False,
                "operatore_nazionale_senza_riferimento_locale",
                [],
                local,
                filter_version,
                False,
            )
        if mobility or obstacle:
            return RelevanceDecision(
                True,
                "operatore_di_trasporto_pertinente",
                sorted(set(mobility + obstacle))[:20],
                local,
                filter_version,
                bool(obstacle),
            )
        return RelevanceDecision(
            False, "operatore_senza_parola_mobilita", [], local, filter_version, False
        )

    return RelevanceDecision(False, "classe_fonte_non_gestita", [], local, filter_version, False)


__all__ = ["RelevanceDecision", "assess_relevance"]
