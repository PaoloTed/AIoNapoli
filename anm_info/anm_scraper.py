#!/usr/bin/env python3
"""
Scraper delle notizie ANM (Azienda Napoletana Mobilita).

ANM non espone un feed RSS o una API pubblica documentata per le notizie.
La pagina pubblica "Notizia Home" e' una Salesforce Experience Cloud app che
carica i record tramite due azioni Aura/Apex raggiungibili pubblicamente:

  - listViewNotiziaHomeController.getNotizie
  - listViewNotiziaHomeController.getNotiziaDetails

Questo script usa gli stessi endpoint, normalizza i campi Salesforce in un
JSON pulito e gestisce errori di rete, HTTP, protocollo e singoli articoli.

Esempi:
    python3 anm_scraper.py
    python3 anm_scraper.py --output anm_news.json --limit 10
    python3 anm_scraper.py --no-details --since 2026-11-01
    python3 anm_scraper.py --output - --compact

Dipendenze:
    python3 -m pip install requests beautifulsoup4

Exit code:
    0  successo completo
    1  errore fatale (nessun JSON scritto)
    2  successo parziale (JSON scritto, ma alcuni dettagli sono falliti)
"""

from __future__ import annotations

import argparse
import concurrent.futures
import html
import itertools
import json
import logging
import os
import random
import re
import sys
import threading
import time
import unicodedata
from datetime import date, datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import quote, unquote, urljoin
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError as exc:  # pragma: no cover - dipende dall'ambiente
    raise SystemExit(
        "Dipendenze mancanti: "
        f"{exc}. Installa con: python3 -m pip install requests beautifulsoup4"
    ) from exc


# ---------------------------------------------------------------------------
# Costanti
# ---------------------------------------------------------------------------

SCRAPER_VERSION = "1.0.0"
SOURCE_NAME = "ANM"
SOURCE_LEGAL_NAME = "ANM S.p.A."
SOURCE_URL = "https://www.anm.it/s/notizia-home/Notizia_Home__c/Default?language=it"
BASE_URL = "https://www.anm.it"
AURA_ENDPOINT = f"{BASE_URL}/s/sfsites/aura"
LIST_PAGE_PATH = "/s/notizia-home/Notizia_Home__c/Default?language=it"
APEX_CLASS = "listViewNotiziaHomeController"

DEFAULT_USER_AGENT = (
    "ANM-News-Scraper/1.0 "
    "(monitoraggio pubblico; +https://www.anm.it/s/notizia-home/)"
)

# Fallback usati solo se il bootstrap dinamico della pagina non riesce.
# I valori possono cambiare quando ANM pubblica una nuova versione del sito.
DEFAULT_FWUID = (
    "NjZ1S2dpaDFCTURrSEliQmh0ZXRhZ2tVMjdnTGFERUU2S3FfSVdrcU92bkExNS4zLjE2MDEw"
)
DEFAULT_LOADED = {
    "APPLICATION@markup://siteforce:communityApp": "1913_ebdeTt9njw4JArw_mL8PvA"
}

ZERO_WIDTH_TRANSLATION = str.maketrans(
    "", "", "\ufeff\u200b\u200c\u200d\u200e\u200f"
)

RETRYABLE_STATUS = frozenset({408, 425, 429, 500, 502, 503, 504})
TRANSIENT_EXCEPTIONS = (
    requests.Timeout,
    requests.ConnectionError,
    requests.exceptions.ChunkedEncodingError,
    requests.exceptions.ContentDecodingError,
)

BLOCK_TAGS = frozenset(
    {
        "address",
        "article",
        "aside",
        "blockquote",
        "div",
        "dl",
        "dt",
        "dd",
        "fieldset",
        "figcaption",
        "figure",
        "footer",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "header",
        "hr",
        "li",
        "main",
        "nav",
        "ol",
        "p",
        "pre",
        "section",
        "table",
        "tbody",
        "td",
        "tfoot",
        "th",
        "thead",
        "tr",
        "ul",
    }
)

CATEGORY_PATTERNS: dict[str, re.Pattern[str]] = {
    "sciopero": re.compile(r"\bsciopero\b|\bscioperi\b|\bastensione\b|\bsindacat", re.I),
    "metro": re.compile(
        r"\bmetro\b|\bmetropolitana\b|\blinea\s*(?:l)?\s*[16]\b|\bfunicolare\b", re.I
    ),
    "bus": re.compile(
        r"\bbus\b|\bautobus\b|\bdeviazione\b|\bcapolinea\b|"
        r"\blinee?\s+(?!(?:l|m)\s*\d)(?:\d{2,4}|[a-z]\d{1,3})\b",
        re.I,
    ),
    "tram": re.compile(r"\btram\b|\btranviar", re.I),
    "alibus": re.compile(r"\balibus\b|\baeroporto\b|\bcapodichino\b", re.I),
    "accessibilita": re.compile(
        r"\baccessibil|\bascensor|\bimpianto\b|\bscala mobile\b|\belevator\b", re.I
    ),
    "meteo": re.compile(
        r"\ballerta\b|\bmeteo\b|\bmaltempo\b|\bidrogeolog|\btemporale\b|\bvento\b", re.I
    ),
    "evento": re.compile(
        r"\bmanifestazione\b|\bevento\b|\bpartita\b|\bconcerto\b|\bregata\b|"
        r"\bmostra\b|\bcontest\b|\bfesta\b",
        re.I,
    ),
    "lavori": re.compile(r"\blavori\b|\bcantiere\b|\brifunzionalizzazione\b", re.I),
    "tariffe": re.compile(
        r"\btariff|\bbigliett|\babbonament|\btitoli di viaggio\b", re.I
    ),
    "parcheggio": re.compile(r"\bparchegg", re.I),
    "servizio": re.compile(
        r"\bvariazione\b|\bmodifica\b|\blimitazione\b|\bripristino\b|"
        r"\bchiusura\b|\banticipa\b|\bdeviazione\b|\bistituite\b|"
        r"\battiva\b|\briapre\b",
        re.I,
    ),
}

logger = logging.getLogger("anm_scraper")


# ---------------------------------------------------------------------------
# Errori
# ---------------------------------------------------------------------------


class ScraperError(RuntimeError):
    """Errore applicativo del scraper."""


class NetworkError(ScraperError):
    """Errore di rete dopo tutti i tentativi."""


class HttpStatusError(ScraperError):
    """Risposta HTTP non valida."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        url: str | None = None,
        content_type: str | None = None,
        snippet: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.url = url
        self.content_type = content_type
        self.snippet = snippet


class ProtocolError(ScraperError):
    """Risposta ricevuta, ma non conforme al protocollo atteso."""


class AuraActionError(ScraperError):
    """Azione Aura/Apex conclusa con errore applicativo."""


class AuraSessionExpired(AuraActionError):
    """Sessione/contesto Aura non piu' valido: va rifatto il bootstrap."""


# ---------------------------------------------------------------------------
# Utility di normalizzazione
# ---------------------------------------------------------------------------


def clean_text(value: Any) -> str | None:
    """Normalizza un valore testuale; restituisce None se vuoto."""
    if value is None:
        return None
    if not isinstance(value, str):
        value = str(value)
    value = html.unescape(value)
    value = value.replace("\u00a0", " ")
    value = value.translate(ZERO_WIDTH_TRANSLATION)
    value = re.sub(r"\s+", " ", value).strip()
    return value or None


def parse_anm_date(value: Any) -> str | None:
    """Converte le date ANM in ISO YYYY-MM-DD; None se non valida."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    text = str(value).strip()
    if not text:
        return None

    # Caso normale: Data__c = "2026-11-12"
    match = re.match(r"^(\d{4})-(\d{2})-(\d{2})", text)
    if match:
        try:
            return date(
                int(match.group(1)), int(match.group(2)), int(match.group(3))
            ).isoformat()
        except ValueError:
            return None

    for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def slugify_anm(text: str | None) -> str:
    """
    Riproduce lo slug usato dal sito ANM, mantenendo le lettere accentate.

    Salesforce/ANM elimina la punteggiatura (compresi i trattini) e trasforma
    solo gli spazi in trattini. Esempio:
      "LINEE 140-151-R7-N1" -> "linee-140151r7n1"
      "PISCINOLA-C. DIREZIONALE" -> "piscinolac-direzionale"
    """
    if not text:
        return ""
    value = unicodedata.normalize("NFC", str(text)).lower()
    value = "".join(
        character
        for character in value
        if character.isalnum() or character.isspace()
    )
    value = re.sub(r"\s+", "-", value).strip("-")
    return value


def article_url(record_id: str, name: str | None) -> str:
    """Costruisce l'URL canonico dell'articolo (con redirect di sicurezza)."""
    slug = slugify_anm(name)
    if slug:
        return (
            f"{BASE_URL}/s/notizia-home/{quote(record_id, safe='')}/"
            f"{quote(slug, safe='')}?language=it"
        )
    return f"{BASE_URL}/s/notizia-home/{quote(record_id, safe='')}?language=it"


def extract_categories(*texts: str | None) -> list[str]:
    """Assegna categorie euristiche in base a titolo, sintesi e corpo."""
    haystack = " ".join(text for text in texts if text)
    if not haystack:
        return ["altro"]
    categories = [
        name for name, pattern in CATEGORY_PATTERNS.items() if pattern.search(haystack)
    ]
    return categories or ["altro"]


def _extract_text_from_soup(soup: BeautifulSoup) -> str | None:
    """Estrae testo leggibile preservando i confini tra blocchi."""
    for tag in soup(["script", "style", "noscript", "template"]):
        tag.decompose()

    for br in soup.find_all("br"):
        br.replace_with("\n")

    for tag in soup.find_all(BLOCK_TAGS):
        tag.insert_before("\n")
        tag.insert_after("\n")

    text = unicodedata.normalize("NFKC", soup.get_text(" "))
    text = text.translate(ZERO_WIDTH_TRANSLATION)
    lines: list[str] = []
    for line in text.splitlines():
        line = re.sub(r"\s+", " ", line).strip()
        line = re.sub(r"\s+([,.;:!?])", r"\1", line)
        line = re.sub(r"([(\[])\s+", r"\1", line)
        line = re.sub(r"\s+([)\]])", r"\1", line)
        if line:
            lines.append(line)
    return "\n".join(lines) or None


def html_to_text(fragment: str | None) -> str | None:
    """Converte un frammento HTML in testo pulito."""
    if not fragment:
        return None
    soup = BeautifulSoup(fragment, "html.parser")
    return _extract_text_from_soup(soup)


def sanitize_body(fragment: str | None) -> tuple[str | None, str | None, list[str]]:
    """
    Pulisce l'HTML del corpo, estrae il testo e le immagini.

    Non esegue script e rimuove attributi pericolosi, mantenendo la formattazione
    utile (paragrafi, grassetti, elenchi, link).
    """
    if not fragment:
        return None, None, []

    soup = BeautifulSoup(fragment, "html.parser")
    for tag in soup(
        ["script", "style", "noscript", "template", "iframe", "object", "embed", "form"]
    ):
        tag.decompose()

    images: list[str] = []
    for img in soup.find_all("img"):
        src = img.get("src")
        if not isinstance(src, str):
            continue
        src = src.strip()
        if not src:
            continue
        absolute = urljoin(f"{BASE_URL}/", src)
        if absolute.lower().startswith(("http://", "https://")):
            images.append(absolute)
            img["src"] = absolute

    for tag in soup.find_all(True):
        for attr in list(tag.attrs):
            lower = attr.lower()
            if lower.startswith("on") or lower in {"srcdoc", "formaction"}:
                del tag.attrs[attr]
            elif lower in {"href", "src", "action"}:
                value = tag.attrs.get(attr)
                if isinstance(value, list):
                    value = " ".join(str(item) for item in value)
                if not isinstance(value, str):
                    continue
                stripped = value.strip()
                if stripped.lower().startswith(("javascript:", "data:", "vbscript:")):
                    del tag.attrs[attr]
                    continue
                if lower == "href":
                    if stripped and not stripped.startswith("#") and not stripped.lower().startswith(
                        ("http://", "https://", "mailto:", "tel:")
                    ):
                        tag.attrs[attr] = urljoin(f"{BASE_URL}/", stripped)
                elif lower == "src" and stripped and not stripped.lower().startswith(
                    ("http://", "https://")
                ):
                    tag.attrs[attr] = urljoin(f"{BASE_URL}/", stripped)

    html_clean = str(soup).strip() or None
    text = _extract_text_from_soup(BeautifulSoup(str(soup), "html.parser"))

    # Deduplica le immagini mantenendo l'ordine.
    unique_images = list(dict.fromkeys(images))
    return html_clean, text, unique_images


def format_aura_errors(errors: Any) -> str:
    """Rende leggibile la struttura errori di Aura."""
    if not errors:
        return ""

    messages: list[str] = []
    if isinstance(errors, list):
        for item in errors:
            if isinstance(item, dict):
                message = (
                    item.get("message")
                    or item.get("exceptionMessage")
                    or item.get("statusCode")
                    or item.get("errorCode")
                )
                if message:
                    messages.append(str(message))
                else:
                    messages.append(json.dumps(item, ensure_ascii=False)[:500])
            elif item:
                messages.append(str(item))
    elif isinstance(errors, dict):
        message = (
            errors.get("message")
            or errors.get("exceptionMessage")
            or errors.get("statusCode")
        )
        messages.append(str(message) if message else json.dumps(errors, ensure_ascii=False))
    elif errors:
        messages.append(str(errors))

    return "; ".join(messages)


# ---------------------------------------------------------------------------
# Retry / rate limiting
# ---------------------------------------------------------------------------


def _parse_retry_after(value: str | None) -> float | None:
    if not value:
        return None
    value = value.strip()
    try:
        return max(0.0, float(value))
    except ValueError:
        pass
    try:
        when = parsedate_to_datetime(value)
        if when.tzinfo is None:
            when = when.replace(tzinfo=datetime.now().astimezone().tzinfo)
        return max(0.0, (when - datetime.now(when.tzinfo)).total_seconds())
    except (TypeError, ValueError, OverflowError):
        return None


class RateLimiter:
    """Limita la frequenza globale di avvio delle richieste."""

    def __init__(self, min_interval: float) -> None:
        self.min_interval = max(0.0, min_interval)
        self._lock = threading.Lock()
        self._next_at = 0.0

    def wait(self) -> None:
        if self.min_interval <= 0:
            return
        with self._lock:
            now = time.monotonic()
            delay = max(0.0, self._next_at - now)
            self._next_at = max(now, self._next_at) + self.min_interval
        if delay:
            time.sleep(delay)


# ---------------------------------------------------------------------------
# Client Aura
# ---------------------------------------------------------------------------


class AuraClient:
    """Client minimale per le azioni Aura/Apex pubbliche del sito ANM."""

    def __init__(
        self,
        *,
        timeout: float = 20.0,
        retries: int = 3,
        backoff: float = 1.0,
        max_retry_wait: float = 30.0,
        user_agent: str = DEFAULT_USER_AGENT,
        rate_limiter: RateLimiter | None = None,
    ) -> None:
        self.timeout = timeout
        self.retries = retries
        self.backoff = backoff
        self.max_retry_wait = max_retry_wait
        self.user_agent = user_agent
        self.rate_limiter = rate_limiter or RateLimiter(0.0)

        self._local = threading.local()
        self._context_lock = threading.Lock()
        self._request_counter = itertools.count(1)
        self._bootstrap_done = False
        self._fwuid: str | None = None
        self._loaded: dict[str, Any] | None = None

    # -- sessioni ---------------------------------------------------------

    def _new_session(self) -> requests.Session:
        session = requests.Session()
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=4, pool_maxsize=8, max_retries=0
        )
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        session.headers.update(
            {
                "User-Agent": self.user_agent,
                "Accept-Language": "it-IT,it;q=0.9,en;q=0.5",
                "Accept-Encoding": "gzip, deflate",
            }
        )
        return session

    def _session(self) -> requests.Session:
        session = getattr(self._local, "session", None)
        if session is None:
            session = self._new_session()
            self._local.session = session
        return session

    # -- HTTP con retry ---------------------------------------------------

    def _sleep_before_retry(self, attempt: int, response: requests.Response | None = None) -> float:
        wait = None
        if response is not None:
            wait = _parse_retry_after(response.headers.get("Retry-After"))
        if wait is None:
            base = self.backoff * (2 ** (attempt - 1))
            jitter = random.uniform(0, max(0.0, self.backoff * 0.25))
            wait = base + jitter
        wait = min(max(0.0, wait), self.max_retry_wait)
        time.sleep(wait)
        return wait

    def _request(self, method: str, url: str, **kwargs: Any) -> requests.Response:
        last_exception: Exception | None = None

        for attempt in range(1, self.retries + 2):
            try:
                response = self._session().request(
                    method,
                    url,
                    timeout=self.timeout,
                    allow_redirects=True,
                    **kwargs,
                )
            except TRANSIENT_EXCEPTIONS as exc:
                last_exception = exc
                if attempt > self.retries:
                    raise NetworkError(
                        f"{method} {url}: errore di rete dopo {attempt} tentativi: {exc}"
                    ) from exc
                wait = self._sleep_before_retry(attempt)
                logger.warning(
                    "Errore di rete (%s) su %s; nuovo tentativo tra %.1fs [%d/%d]",
                    type(exc).__name__,
                    url,
                    wait,
                    attempt,
                    self.retries,
                )
                continue
            except requests.RequestException as exc:
                raise NetworkError(f"{method} {url}: richiesta fallita: {exc}") from exc

            if response.status_code in RETRYABLE_STATUS and attempt <= self.retries:
                wait = self._sleep_before_retry(attempt, response)
                logger.warning(
                    "HTTP %s da %s; nuovo tentativo tra %.1fs [%d/%d]",
                    response.status_code,
                    url,
                    wait,
                    attempt,
                    self.retries,
                )
                response.close()
                continue

            if response.status_code >= 400:
                snippet = ""
                try:
                    snippet = response.text[:300].replace("\n", " ").strip()
                except Exception:
                    pass
                content_type = response.headers.get("Content-Type")
                response.close()
                raise HttpStatusError(
                    f"{method} {url}: HTTP {response.status_code}"
                    + (f" ({content_type})" if content_type else "")
                    + (f" - {snippet!r}" if snippet else ""),
                    status_code=response.status_code,
                    url=url,
                    content_type=content_type,
                    snippet=snippet,
                )

            return response

        raise NetworkError(
            f"{method} {url}: esauriti i tentativi"
            + (f": {last_exception}" if last_exception else "")
        )

    # -- bootstrap del contesto Aura -------------------------------------

    @staticmethod
    def _parse_bootstrap_context(html_text: str) -> tuple[str | None, dict[str, Any] | None]:
        fwuid: str | None = None
        loaded: dict[str, Any] | None = None

        # Il contesto serializzato e' presente nei link /s/sfsites/l/<JSON>/.
        for encoded in re.findall(r"/s/sfsites/l/([^/]+)/", html_text):
            try:
                candidate = json.loads(unquote(encoded))
            except (ValueError, TypeError):
                continue
            if not isinstance(candidate, dict):
                continue
            if isinstance(candidate.get("fwuid"), str):
                fwuid = candidate["fwuid"]
            if isinstance(candidate.get("loaded"), dict):
                loaded = candidate["loaded"]
            if fwuid and loaded:
                break

        if not fwuid:
            match = re.search(
                r"/s/sfsites/auraFW/javascript/([^/]+)/aura_prod\.js", html_text
            )
            if match:
                fwuid = match.group(1)

        return fwuid, loaded

    def bootstrap(self, *, force: bool = False) -> None:
        """Recupera fwuid e versione applicativa dalla pagina pubblica."""
        with self._context_lock:
            if self._bootstrap_done and not force:
                return

            logger.debug("Bootstrap contesto Aura da %s", SOURCE_URL)
            try:
                response = self._request(
                    "GET",
                    SOURCE_URL,
                    headers={
                        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                        "Referer": f"{BASE_URL}/",
                    },
                )
                try:
                    fwuid, loaded = self._parse_bootstrap_context(response.text)
                finally:
                    response.close()
            except ScraperError as exc:
                fwuid, loaded = None, None
                logger.warning("Bootstrap non riuscito: %s", exc)

            if not fwuid or not loaded:
                if DEFAULT_FWUID and DEFAULT_LOADED:
                    logger.warning(
                        "Contesto Aura non estratto; uso il fallback incorporato "
                        "(potrebbe essere superato)."
                    )
                    fwuid, loaded = DEFAULT_FWUID, DEFAULT_LOADED
                else:  # pragma: no cover - i fallback sono definiti
                    raise ProtocolError(
                        "Impossibile estrarre fwuid/loaded dalla pagina ANM"
                    )

            self._fwuid = fwuid
            self._loaded = loaded
            self._bootstrap_done = True

    # -- chiamata azione --------------------------------------------------

    def _context_json(self) -> str:
        if not self._bootstrap_done:
            self.bootstrap()
        with self._context_lock:
            fwuid = self._fwuid
            loaded = self._loaded or DEFAULT_LOADED
        context = {
            "mode": "PROD",
            "fwuid": fwuid,
            "app": "siteforce:communityApp",
            "loaded": loaded,
            "dn": [],
            "globals": {},
            "uad": True,
        }
        return json.dumps(context, ensure_ascii=False, separators=(",", ":"))

    @staticmethod
    def _extract_action_result(payload: Any, classname: str, method: str) -> Any:
        if not isinstance(payload, dict):
            raise ProtocolError(
                f"{classname}.{method}: risposta Aura non oggetto: "
                f"{type(payload).__name__}"
            )

        event = payload.get("event")
        if isinstance(event, dict):
            descriptor = event.get("descriptor") or "evento sconosciuto"
            if "invalidSession" in descriptor or "session" in descriptor.lower():
                raise AuraSessionExpired(
                    f"{classname}.{method}: sessione Aura scaduta ({descriptor})"
                )
            raise AuraActionError(f"{classname}.{method}: evento Aura inatteso: {descriptor}")

        actions = payload.get("actions")
        if not isinstance(actions, list) or not actions:
            raise ProtocolError(
                f"{classname}.{method}: campo 'actions' assente o vuoto: "
                f"{str(payload)[:300]}"
            )

        action = actions[0]
        if not isinstance(action, dict):
            raise ProtocolError(f"{classname}.{method}: azione Aura non valida")

        state = action.get("state")
        if state != "SUCCESS":
            message = format_aura_errors(action.get("error")) or str(state or "")
            lowered = message.lower()
            if "invalidsession" in lowered or (
                "session" in lowered and ("expired" in lowered or "scadut" in lowered)
            ):
                raise AuraSessionExpired(
                    f"{classname}.{method}: sessione Aura scaduta: {message}"
                )
            raise AuraActionError(
                f"{classname}.{method}: stato {state!r}: {message or 'errore sconosciuto'}"
            )

        return_value = action.get("returnValue")
        if isinstance(return_value, dict) and "returnValue" in return_value:
            return return_value["returnValue"]
        return return_value

    def _call_action(
        self,
        classname: str,
        method: str,
        params: dict[str, Any] | None = None,
        *,
        cacheable: bool = False,
    ) -> Any:
        self.bootstrap()
        request_number = next(self._request_counter)
        action = {
            "id": "1;a",
            "descriptor": "aura://ApexActionController/ACTION$execute",
            "callingDescriptor": "UNKNOWN",
            "params": {
                "namespace": "",
                "classname": classname,
                "method": method,
                "params": params or {},
                "cacheable": cacheable,
                "isContinuation": False,
            },
        }
        message = json.dumps({"actions": [action]}, ensure_ascii=False, separators=(",", ":"))
        data = {
            "message": message,
            "aura.context": self._context_json(),
            "aura.pageURI": LIST_PAGE_PATH,
            "aura.token": "null",
        }
        url = f"{AURA_ENDPOINT}?r={request_number}&aura.ApexAction.execute=1"

        self.rate_limiter.wait()
        response = self._request(
            "POST",
            url,
            data=data,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                "Origin": BASE_URL,
                "Referer": SOURCE_URL,
                "X-SFDC-LDS-Endpoints": f"ApexActionController.execute:{classname}.{method}",
            },
        )

        content_type = response.headers.get("Content-Type", "")
        body_start = ""
        try:
            body_start = response.text.lstrip()[:1]
        except Exception:
            pass
        if "json" not in content_type.lower() and body_start != "{":
            snippet = ""
            try:
                snippet = response.text[:300].replace("\n", " ").strip()
            except Exception:
                pass
            response.close()
            raise ProtocolError(
                f"{classname}.{method}: atteso JSON, ricevuto "
                f"Content-Type={content_type!r} - {snippet!r}"
            )

        try:
            payload = response.json()
        except ValueError as exc:
            snippet = ""
            try:
                snippet = response.text[:300].replace("\n", " ").strip()
            except Exception:
                pass
            response.close()
            raise ProtocolError(
                f"{classname}.{method}: JSON non valido - {snippet!r}"
            ) from exc
        finally:
            response.close()

        return self._extract_action_result(payload, classname, method)

    def call_action(
        self,
        classname: str,
        method: str,
        params: dict[str, Any] | None = None,
        *,
        cacheable: bool = False,
    ) -> Any:
        """Esegue un'azione, rifacendo il bootstrap una volta se la sessione scade."""
        try:
            return self._call_action(classname, method, params, cacheable=cacheable)
        except AuraSessionExpired:
            logger.warning("Sessione Aura scaduta; aggiorno il contesto e riprovo.")
            self.bootstrap(force=True)
            return self._call_action(classname, method, params, cacheable=cacheable)

    # -- API ANM ----------------------------------------------------------

    def get_notizie(self) -> list[dict[str, Any]]:
        result = self.call_action(APEX_CLASS, "getNotizie", {}, cacheable=True)
        if not isinstance(result, list):
            raise ProtocolError(
                "getNotizie: attesa una lista, ricevuto "
                f"{type(result).__name__}: {str(result)[:300]}"
            )
        return [item for item in result if isinstance(item, dict)]

    def get_notizia_details(self, record_id: str) -> dict[str, Any]:
        result = self.call_action(
            APEX_CLASS,
            "getNotiziaDetails",
            {"recordId": record_id},
            cacheable=False,
        )
        if not isinstance(result, dict):
            raise ProtocolError(
                f"getNotiziaDetails({record_id}): atteso un oggetto, ricevuto "
                f"{type(result).__name__}"
            )
        returned_id = clean_text(result.get("Id"))
        if returned_id and returned_id != record_id:
            raise ProtocolError(
                f"getNotiziaDetails({record_id}): il server ha restituito "
                f"il record {returned_id}"
            )
        return result


# ---------------------------------------------------------------------------
# Normalizzazione articoli
# ---------------------------------------------------------------------------


def normalize_article(
    record: dict[str, Any],
    *,
    detail: dict[str, Any] | None = None,
    detail_error: str | None = None,
) -> dict[str, Any]:
    """Trasforma un record Salesforce in un articolo JSON pulito."""
    record_id = clean_text(record.get("Id")) or ""
    name = clean_text(record.get("Name"))
    title = clean_text(record.get("Titolo__c")) or name or "(senza titolo)"
    title_en = clean_text(record.get("Titolo_Inglese__c"))
    published_date = parse_anm_date(record.get("Data__c"))
    summary = clean_text(record.get("Sintesi1__c"))
    if summary and re.search(r"<\s*[a-zA-Z/]", summary):
        summary = html_to_text(summary) or summary
    summary_en = clean_text(record.get("Sintesi_Inglese__c"))
    if summary_en and re.search(r"<\s*[a-zA-Z/]", summary_en):
        summary_en = html_to_text(summary_en) or summary_en

    body_html: str | None = None
    body_text: str | None = None
    body_html_en: str | None = None
    body_text_en: str | None = None
    images: list[str] = []
    body_source = "unavailable"

    if detail:
        body_html, body_text, images_it = sanitize_body(detail.get("Notizia__c"))
        body_html_en, body_text_en, images_en = sanitize_body(
            detail.get("Notizia_Inglese__c")
        )
        images = list(dict.fromkeys(images_it + images_en))
        if body_text or body_html or body_text_en or body_html_en:
            body_source = "detail"

    if not body_text and summary:
        body_text = summary
        body_source = "summary" if body_source != "detail" else body_source
    if not body_text_en and summary_en:
        body_text_en = summary_en
    if not body_text and not body_text_en and body_source != "detail":
        body_source = "unavailable"

    categories = extract_categories(title, summary, body_text)

    return {
        "id": record_id,
        "title": title,
        "title_en": title_en,
        "date": published_date,
        "summary": summary,
        "summary_en": summary_en,
        "body_html": body_html,
        "body_text": body_text,
        "body_html_en": body_html_en,
        "body_text_en": body_text_en,
        "images": images,
        "url": article_url(record_id, name or title) if record_id else None,
        "categories": categories,
        "source": SOURCE_NAME,
        "body_source": body_source,
        "detail_error": detail_error,
    }


# ---------------------------------------------------------------------------
# Scraping
# ---------------------------------------------------------------------------


def _record_sort_key(record: dict[str, Any]) -> tuple[int, str]:
    parsed = parse_anm_date(record.get("Data__c"))
    return (1 if parsed else 0, parsed or "")


def scrape(
    *,
    limit: int | None = None,
    since: date | None = None,
    details: bool = True,
    workers: int = 3,
    delay: float = 0.2,
    timeout: float = 20.0,
    retries: int = 3,
    user_agent: str = DEFAULT_USER_AGENT,
    allow_empty: bool = False,
) -> dict[str, Any]:
    """Esegue lo scraping e restituisce il documento JSON serializzabile."""
    started = time.monotonic()
    errors: list[dict[str, Any]] = []

    client = AuraClient(
        timeout=timeout,
        retries=retries,
        user_agent=user_agent,
        rate_limiter=RateLimiter(delay),
    )

    logger.info("Recupero elenco notizie ANM...")
    client.bootstrap()
    records = client.get_notizie()
    listed_count = len(records)

    if not records and not allow_empty:
        errors.append(
            {
                "scope": "list",
                "severity": "error",
                "message": "ANM ha restituito zero notizie: possibile cambio pagina o blocco.",
            }
        )

    # Validazione minima dei record.
    valid_records: list[dict[str, Any]] = []
    seen_record_ids: set[str] = set()
    for index, record in enumerate(records):
        record_id = clean_text(record.get("Id"))
        if not record_id:
            errors.append(
                {
                    "scope": "list",
                    "severity": "error",
                    "index": index,
                    "message": "Record senza Id Salesforce: ignorato.",
                }
            )
            continue
        if record_id in seen_record_ids:
            errors.append(
                {
                    "scope": "list",
                    "severity": "warning",
                    "article_id": record_id,
                    "message": "Record duplicato: ignorato.",
                }
            )
            continue
        seen_record_ids.add(record_id)
        if not clean_text(record.get("Titolo__c")) and not clean_text(record.get("Name")):
            errors.append(
                {
                    "scope": "list",
                    "severity": "warning",
                    "article_id": record_id,
                    "message": "Record senza titolo: mantenuto con titolo di fallback.",
                }
            )
        valid_records.append(record)

    # Filtro --since. Le date mancanti vengono mantenute per non perdere news.
    if since is not None:
        filtered: list[dict[str, Any]] = []
        for record in valid_records:
            parsed = parse_anm_date(record.get("Data__c"))
            if parsed is None:
                filtered.append(record)
                errors.append(
                    {
                        "scope": "filter",
                        "severity": "warning",
                        "article_id": clean_text(record.get("Id")),
                        "message": "Data mancante o non valida: articolo mantenuto nonostante --since.",
                    }
                )
            elif parsed >= since.isoformat():
                filtered.append(record)
        valid_records = filtered

    valid_records.sort(key=_record_sort_key, reverse=True)

    if limit is not None:
        valid_records = valid_records[:limit]

    logger.info(
        "Notizie trovate: %d; dopo filtri: %d", listed_count, len(valid_records)
    )

    # Dettagli in parallelo, con rate limit globale e degradazione elegante.
    detail_map: dict[str, dict[str, Any]] = {}
    detail_errors: dict[str, str] = {}

    if details and valid_records:
        total = len(valid_records)

        def fetch_detail(record: dict[str, Any]) -> tuple[str, dict[str, Any] | None, str | None]:
            record_id = clean_text(record.get("Id")) or ""
            try:
                return record_id, client.get_notizia_details(record_id), None
            except Exception as exc:  # noqa: BLE001 - un errore non blocca gli altri
                return record_id, None, f"{type(exc).__name__}: {exc}"

        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
            futures = [executor.submit(fetch_detail, record) for record in valid_records]
            for index, future in enumerate(
                concurrent.futures.as_completed(futures), start=1
            ):
                record_id, detail, error = future.result()
                if detail is not None:
                    detail_map[record_id] = detail
                else:
                    message = error or "errore sconosciuto"
                    detail_errors[record_id] = message
                    errors.append(
                        {
                            "scope": "detail",
                            "severity": "error",
                            "article_id": record_id,
                            "message": message,
                        }
                    )
                    logger.warning("Dettaglio non recuperato per %s: %s", record_id, message)
                if index == total or index % 10 == 0:
                    logger.info(
                        "Dettagli recuperati: %d/%d (errori: %d)",
                        index,
                        total,
                        len(detail_errors),
                    )

    articles = [
        normalize_article(
            record,
            detail=detail_map.get(clean_text(record.get("Id")) or ""),
            detail_error=detail_errors.get(clean_text(record.get("Id")) or ""),
        )
        for record in valid_records
    ]

    duration = time.monotonic() - started
    try:
        now = datetime.now(ZoneInfo("Europe/Rome"))
    except ZoneInfoNotFoundError:  # pragma: no cover - dipende dal sistema
        now = datetime.now().astimezone()
    details_ok = len(detail_map)

    document: dict[str, Any] = {
        "meta": {
            "source": SOURCE_NAME,
            "source_legal_name": SOURCE_LEGAL_NAME,
            "source_url": SOURCE_URL,
            "scraper": "anm_scraper.py",
            "scraper_version": SCRAPER_VERSION,
            "scraped_at": now.isoformat(timespec="seconds"),
            "timezone": str(now.tzinfo) if now.tzinfo else None,
            "method": "Salesforce Experience Cloud Aura/Apex action",
            "listed_count": listed_count,
            "exported_count": len(articles),
            "details_requested": bool(details),
            "details_ok": details_ok,
            "details_failed": len(detail_errors),
            "errors_count": sum(
                1 for error in errors if error.get("severity") == "error"
            ),
            "warnings_count": sum(
                1 for error in errors if error.get("severity") == "warning"
            ),
            "duration_seconds": round(duration, 2),
            "filters": {
                "since": since.isoformat() if since is not None else None,
                "limit": limit,
            },
        },
        "articles": articles,
        "errors": errors,
    }
    return document


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------


def write_json(document: dict[str, Any], output: str, *, compact: bool = False) -> None:
    """Scrive il JSON in modo atomico (o su stdout con output '-')."""
    indent = None if compact else 2
    separators = (",", ":") if compact else None

    if output == "-":
        json.dump(
            document,
            sys.stdout,
            ensure_ascii=False,
            indent=indent,
            separators=separators,
        )
        sys.stdout.write("\n")
        return

    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f".{path.name}.tmp.{os.getpid()}")
    try:
        with open(temp_path, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(
                document,
                handle,
                ensure_ascii=False,
                indent=indent,
                separators=separators,
            )
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
    except Exception:
        try:
            temp_path.unlink()
        except OSError:
            pass
        raise


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def positive_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"intero non valido: {value!r}") from exc
    if parsed <= 0:
        raise argparse.ArgumentTypeError("il valore deve essere maggiore di zero")
    return parsed


def non_negative_float(value: str) -> float:
    try:
        parsed = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"numero non valido: {value!r}") from exc
    if parsed < 0:
        raise argparse.ArgumentTypeError("il valore non puo' essere negativo")
    return parsed


def iso_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            f"data non valida: {value!r}; usa YYYY-MM-DD"
        ) from exc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Scarica le notizie ANM dalla pagina Notizia Home e produce JSON pulito. "
            "Non usa API ufficiali: sfrutta le azioni Aura/Apex pubbliche del sito."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "-o",
        "--output",
        default="anm_news.json",
        help="File JSON di uscita; usa '-' per stdout",
    )
    parser.add_argument(
        "--limit",
        type=positive_int,
        default=None,
        help="Numero massimo di articoli da esportare",
    )
    parser.add_argument(
        "--since",
        type=iso_date,
        default=None,
        help="Esporta solo articoli con data >= YYYY-MM-DD",
    )
    parser.add_argument(
        "--no-details",
        action="store_true",
        help="Non scaricare il corpo completo: usa solo elenco e sintesi",
    )
    parser.add_argument(
        "--workers",
        type=positive_int,
        default=3,
        help="Numero di richieste di dettaglio in parallelo (max consigliato: 5)",
    )
    parser.add_argument(
        "--delay",
        type=non_negative_float,
        default=0.2,
        help="Intervallo minimo globale tra richieste di dettaglio, in secondi",
    )
    parser.add_argument(
        "--timeout",
        type=non_negative_float,
        default=20.0,
        help="Timeout per singola richiesta, in secondi",
    )
    parser.add_argument(
        "--retries",
        type=int,
        default=3,
        help="Tentativi aggiuntivi per errori transitori",
    )
    parser.add_argument(
        "--user-agent",
        default=DEFAULT_USER_AGENT,
        help="User-Agent identificabile",
    )
    parser.add_argument(
        "--compact",
        action="store_true",
        help="JSON compatto invece che indentato",
    )
    parser.add_argument(
        "--allow-empty",
        action="store_true",
        help="Non considerare un elenco vuoto come errore",
    )
    verbosity = parser.add_mutually_exclusive_group()
    verbosity.add_argument("-v", "--verbose", action="store_true", help="Log dettagliato")
    verbosity.add_argument("-q", "--quiet", action="store_true", help="Solo errori")
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {SCRAPER_VERSION}",
    )
    return parser


def configure_logging(verbose: bool, quiet: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    if quiet:
        level = logging.ERROR
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stderr,
    )


def main(argv: Iterable[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)

    if args.workers > 8:
        parser.error("--workers non puo' superare 8 (carico eccessivo sul sito)")
    if args.retries < 0 or args.retries > 10:
        parser.error("--retries deve essere tra 0 e 10")
    if args.timeout <= 0:
        parser.error("--timeout deve essere maggiore di zero")

    configure_logging(args.verbose, args.quiet)

    try:
        document = scrape(
            limit=args.limit,
            since=args.since,
            details=not args.no_details,
            workers=args.workers,
            delay=args.delay,
            timeout=args.timeout,
            retries=args.retries,
            user_agent=args.user_agent,
            allow_empty=args.allow_empty,
        )
    except KeyboardInterrupt:
        logger.error("Interrotto dall'utente.")
        return 130
    except ScraperError as exc:
        logger.error("Errore fatale: %s", exc)
        return 1
    except Exception as exc:  # noqa: BLE001 - ultima barriera per un errore chiaro
        logger.exception("Errore imprevisto: %s", exc)
        return 1

    try:
        write_json(document, args.output, compact=args.compact)
    except OSError as exc:
        logger.error("Impossibile scrivere %s: %s", args.output, exc)
        return 1

    meta = document["meta"]
    logger.info(
        "Scritto %s: %d articoli, %d dettagli OK, %d errori, %d avvisi, %.1fs",
        args.output,
        meta["exported_count"],
        meta["details_ok"],
        meta.get("errors_count", 0),
        meta.get("warnings_count", 0),
        meta["duration_seconds"],
    )

    if meta["listed_count"] == 0 and not args.allow_empty:
        logger.error("Elenco vuoto: esito considerato parziale.")
        return 2
    if meta.get("errors_count", 0) > 0:
        logger.warning("Completato con errori parziali (vedi campo 'errors').")
        return 2
    if meta.get("warnings_count", 0) > 0:
        logger.warning("Completato con avvisi non bloccanti (vedi campo 'errors').")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
