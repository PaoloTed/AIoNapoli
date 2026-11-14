#!/usr/bin/env python3
"""Test per anm_scraper.py.

I test unitari non usano la rete. I test live sono abilitati con:

    ANM_LIVE_TEST=1 python3 -m unittest -v test_anm_scraper.py
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

import anm_scraper as scraper


class FakeResponse:
    def __init__(
        self,
        status_code: int = 200,
        *,
        json_data=None,
        text: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.status_code = status_code
        self._json_data = json_data
        self.headers = headers or {}
        if text is None and json_data is not None:
            text = json.dumps(json_data)
        self.text = text or ""
        self.closed = False

    def json(self):
        if isinstance(self._json_data, Exception):
            raise self._json_data
        if self._json_data is None:
            raise ValueError("nessun JSON")
        return self._json_data

    def close(self) -> None:
        self.closed = True


class FakeSession:
    def __init__(self, responses) -> None:
        self.responses = list(responses)
        self.calls: list[tuple[str, str, dict]] = []

    def request(self, method: str, url: str, **kwargs):
        self.calls.append((method, url, kwargs))
        if not self.responses:
            raise AssertionError("FakeSession esaurita")
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def aura_success(return_value):
    return {
        "actions": [
            {
                "state": "SUCCESS",
                "returnValue": {"returnValue": return_value, "cacheable": True},
                "error": [],
            }
        ]
    }


def make_client(*responses) -> tuple[scraper.AuraClient, FakeSession]:
    client = scraper.AuraClient(timeout=1, retries=2, backoff=0.01)
    client._bootstrap_done = True
    client._fwuid = "test-fwuid"
    client._loaded = {"APPLICATION@markup://siteforce:communityApp": "test"}
    session = FakeSession(responses)
    client._local.session = session
    return client, session


class UtilityTests(unittest.TestCase):
    def test_clean_text(self):
        self.assertEqual(scraper.clean_text("  a\n\t b  "), "a b")
        self.assertEqual(scraper.clean_text("\ufeffciao\u200b"), "ciao")
        self.assertEqual(scraper.clean_text("A &amp; B"), "A & B")
        self.assertIsNone(scraper.clean_text("   "))
        self.assertIsNone(scraper.clean_text(None))

    def test_parse_anm_date(self):
        self.assertEqual(scraper.parse_anm_date("2026-11-12"), "2026-11-12")
        self.assertEqual(scraper.parse_anm_date("12/11/2026"), "2026-11-12")
        self.assertEqual(scraper.parse_anm_date("2026-11-12T10:30:00"), "2026-11-12")
        self.assertIsNone(scraper.parse_anm_date("2026-13-40"))
        self.assertIsNone(scraper.parse_anm_date("non una data"))

    def test_slugify_anm(self):
        self.assertEqual(
            scraper.slugify_anm(
                "VARIAZIONI AL SERVIZIO PER L\u2019EVENTO \u201cTRI GOLD\u201d"
            ),
            "variazioni-al-servizio-per-levento-tri-gold",
        )
        self.assertEqual(
            scraper.slugify_anm("LUNEDI' 16 NOVEMBRE SCIOPERO"),
            "lunedi-16-novembre-sciopero",
        )
        self.assertEqual(
            scraper.slugify_anm("UNIVexpò 2026: raggiungi la manifestazione"),
            "univexpò-2026-raggiungi-la-manifestazione",
        )
        self.assertEqual(
            scraper.slugify_anm("LINEE 140-151-R7-N1"),
            "linee-140151r7n1",
        )
        self.assertEqual(
            scraper.slugify_anm("PISCINOLA-C. DIREZIONALE"),
            "piscinolac-direzionale",
        )

    def test_article_url_encodes_unicode(self):
        url = scraper.article_url("a0g123", "UNIVexpò 2026")
        self.assertIn("a0g123", url)
        self.assertIn("univexp%C3%B2-2026", url)
        self.assertTrue(url.endswith("?language=it"))

    def test_html_to_text_preserves_blocks(self):
        html = (
            "<p><strong>Ciao </strong>mondo</p>"
            "<p>Seconda&nbsp;riga<br>nuova riga</p>"
            "<p>\U0001d405\U0001d408\U0001d413</p>"
        )
        text = scraper.html_to_text(html)
        self.assertIn("Ciao mondo", text)
        self.assertIn("Seconda riga", text)
        self.assertIn("nuova riga", text)
        self.assertIn("FIT", text)  # NFKC normalizza i caratteri bold Unicode

    def test_sanitize_body_removes_dangerous_markup(self):
        html = (
            "<p>Testo <strong>forte</strong></p>"
            "<script>alert(1)</script>"
            "<img src='/media/foto.jpg' onerror='alert(2)'>"
            "<a href='javascript:alert(3)'>link</a>"
            "<a href='/s/notizia-home'>notizia</a>"
        )
        clean_html, text, images = scraper.sanitize_body(html)
        self.assertNotIn("<script", clean_html or "")
        self.assertNotIn("onerror", clean_html or "")
        self.assertNotIn("javascript:", clean_html or "")
        self.assertIn('href="https://www.anm.it/s/notizia-home"', clean_html or "")
        self.assertIn("Testo forte", text or "")
        self.assertEqual(images, ["https://www.anm.it/media/foto.jpg"])

    def test_extract_categories(self):
        self.assertIn("sciopero", scraper.extract_categories("SCIOPERO DI 4 ORE"))
        self.assertIn("metro", scraper.extract_categories("METRO L1 CHIUSURA ANTICIPATA"))
        self.assertIn("bus", scraper.extract_categories("DEVIAZIONE LINEA 178"))
        self.assertIn("meteo", scraper.extract_categories("ALLERTA METEO"))
        self.assertEqual(scraper.extract_categories(""), ["altro"])

    def test_format_aura_errors(self):
        self.assertEqual(
            scraper.format_aura_errors([{"message": "boom"}, "secondo"]),
            "boom; secondo",
        )
        self.assertEqual(scraper.format_aura_errors(None), "")


class AuraParsingTests(unittest.TestCase):
    def test_extract_action_result_success(self):
        payload = aura_success([{"Id": "1"}])
        result = scraper.AuraClient._extract_action_result(
            payload, "Cls", "method"
        )
        self.assertEqual(result, [{"Id": "1"}])

    def test_extract_action_result_direct_return_value(self):
        payload = {
            "actions": [
                {"state": "SUCCESS", "returnValue": {"Id": "1"}, "error": []}
            ]
        }
        result = scraper.AuraClient._extract_action_result(
            payload, "Cls", "method"
        )
        self.assertEqual(result, {"Id": "1"})

    def test_extract_action_result_error(self):
        payload = {
            "actions": [
                {
                    "state": "ERROR",
                    "error": [{"message": "record non trovato"}],
                }
            ]
        }
        with self.assertRaises(scraper.AuraActionError) as ctx:
            scraper.AuraClient._extract_action_result(payload, "Cls", "method")
        self.assertIn("record non trovato", str(ctx.exception))

    def test_extract_action_result_invalid_session(self):
        payload = {
            "event": {
                "descriptor": "markup://aura:invalidSession",
                "attributes": {"values": {}},
            }
        }
        with self.assertRaises(scraper.AuraSessionExpired):
            scraper.AuraClient._extract_action_result(payload, "Cls", "method")

    def test_parse_bootstrap_context(self):
        encoded = (
            "%7B%22mode%22%3A%22PROD%22%2C%22fwuid%22%3A%22fw%22%2C"
            "%22loaded%22%3A%7B%22APPLICATION%40markup%3A%2F%2Fsiteforce"
            "%3AcommunityApp%22%3A%22v1%22%7D%7D"
        )
        html = f'<a href="/s/sfsites/l/{encoded}/app.js">x</a>'
        fwuid, loaded = scraper.AuraClient._parse_bootstrap_context(html)
        self.assertEqual(fwuid, "fw")
        self.assertEqual(
            loaded, {"APPLICATION@markup://siteforce:communityApp": "v1"}
        )


class RequestRetryTests(unittest.TestCase):
    def test_retries_500_then_success(self):
        client, session = make_client(
            FakeResponse(500, text="errore"),
            FakeResponse(200, json_data={"ok": True}),
        )
        with mock.patch("anm_scraper.time.sleep", return_value=None):
            response = client._request("GET", "https://example.test")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(session.calls), 2)

    def test_does_not_retry_404(self):
        client, session = make_client(FakeResponse(404, text="not found"))
        with mock.patch("anm_scraper.time.sleep", return_value=None):
            with self.assertRaises(scraper.HttpStatusError) as ctx:
                client._request("GET", "https://example.test")
        self.assertEqual(ctx.exception.status_code, 404)
        self.assertEqual(len(session.calls), 1)

    def test_retries_network_error_then_success(self):
        client, session = make_client(
            scraper.requests.ConnectionError("connessione persa"),
            FakeResponse(200, json_data={"ok": True}),
        )
        with mock.patch("anm_scraper.time.sleep", return_value=None):
            response = client._request("GET", "https://example.test")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(session.calls), 2)

    def test_gives_up_after_retries(self):
        client, session = make_client(
            scraper.requests.Timeout("timeout"),
            scraper.requests.Timeout("timeout"),
            scraper.requests.Timeout("timeout"),
        )
        with mock.patch("anm_scraper.time.sleep", return_value=None):
            with self.assertRaises(scraper.NetworkError):
                client._request("GET", "https://example.test")
        self.assertEqual(len(session.calls), 3)

    def test_rejects_non_json_response(self):
        client, _ = make_client(
            FakeResponse(
                200,
                text="<html>challenge</html>",
                headers={"Content-Type": "text/html"},
            )
        )
        with self.assertRaises(scraper.ProtocolError):
            client._call_action("Cls", "method")


class AnmApiTests(unittest.TestCase):
    def test_get_notizie_unwraps_list(self):
        records = [{"Id": "a0g1", "Titolo__c": "Titolo"}]
        client, session = make_client(
            FakeResponse(
                200,
                json_data=aura_success(records),
                headers={"Content-Type": "application/json"},
            )
        )
        result = client.get_notizie()
        self.assertEqual(result, records)
        self.assertEqual(session.calls[0][0], "POST")
        self.assertIn("aura.ApexAction.execute=1", session.calls[0][1])

    def test_get_notizia_details_rejects_wrong_id(self):
        client, _ = make_client(
            FakeResponse(
                200,
                json_data=aura_success({"Id": "altro", "Notizia__c": "<p>x</p>"}),
                headers={"Content-Type": "application/json"},
            )
        )
        with self.assertRaises(scraper.ProtocolError):
            client.get_notizia_details("atteso")

    def test_get_notizia_details_success(self):
        detail = {"Id": "a0g1", "Notizia__c": "<p>Corpo</p>"}
        client, _ = make_client(
            FakeResponse(
                200,
                json_data=aura_success(detail),
                headers={"Content-Type": "application/json"},
            )
        )
        self.assertEqual(client.get_notizia_details("a0g1"), detail)


class NormalizationTests(unittest.TestCase):
    def test_normalize_article_with_detail(self):
        record = {
            "Id": "a0g1",
            "Name": "DEVIAZIONE LINEA 178",
            "Titolo__c": "DEVIAZIONE LINEA 178",
            "Data__c": "2026-11-12",
            "Sintesi1__c": "Sintesi breve",
        }
        detail = {
            "Id": "a0g1",
            "Notizia__c": "<p>Corpo <strong>completo</strong></p>",
            "Notizia_Inglese__c": "<p>Full <strong>body</strong></p>",
        }
        article = scraper.normalize_article(record, detail=detail)
        self.assertEqual(article["id"], "a0g1")
        self.assertEqual(article["date"], "2026-11-12")
        self.assertEqual(article["body_source"], "detail")
        self.assertIn("Corpo completo", article["body_text"])
        self.assertIn("Full body", article["body_text_en"])
        self.assertIn("bus", article["categories"])
        self.assertEqual(article["source"], "ANM")
        self.assertTrue(article["url"].startswith("https://www.anm.it/"))

    def test_normalize_article_cleans_html_summary(self):
        record = {
            "Id": "a0g3",
            "Name": "AVVISO",
            "Titolo__c": "AVVISO",
            "Data__c": "2026-11-12",
            "Sintesi1__c": "<p>Testo <strong>forte</strong></p>",
        }
        article = scraper.normalize_article(record)
        self.assertEqual(article["summary"], "Testo forte")

    def test_normalize_article_falls_back_to_summary(self):
        record = {
            "Id": "a0g2",
            "Name": "SCIOPERO",
            "Titolo__c": "SCIOPERO",
            "Data__c": "2026-11-12",
            "Sintesi1__c": "Sintesi di fallback",
        }
        article = scraper.normalize_article(
            record, detail=None, detail_error="timeout"
        )
        self.assertEqual(article["body_source"], "summary")
        self.assertEqual(article["body_text"], "Sintesi di fallback")
        self.assertEqual(article["detail_error"], "timeout")


class ScrapeTests(unittest.TestCase):
    @staticmethod
    def _records():
        return [
            {
                "Id": "a0g_old",
                "Name": "SCIOPERO",
                "Titolo__c": "SCIOPERO",
                "Data__c": "2026-11-01",
                "Sintesi1__c": "Vecchia",
            },
            {
                "Id": "a0g_new",
                "Name": "METRO L1",
                "Titolo__c": "METRO L1",
                "Data__c": "2026-11-12",
                "Sintesi1__c": "Nuova",
            },
        ]

    def test_limit_and_since(self):
        with mock.patch.object(scraper.AuraClient, "bootstrap", return_value=None), \
             mock.patch.object(
                 scraper.AuraClient, "get_notizie", return_value=self._records()
             ):
            doc = scraper.scrape(
                details=False,
                since=date(2026, 11, 10),
                limit=1,
                delay=0,
            )
        self.assertEqual(doc["meta"]["listed_count"], 2)
        self.assertEqual(doc["meta"]["exported_count"], 1)
        self.assertEqual(doc["articles"][0]["id"], "a0g_new")

    def test_partial_detail_failure_is_graceful(self):
        records = self._records()

        def fake_details(record_id):
            if record_id == "a0g_old":
                raise scraper.ProtocolError("dettaglio non disponibile")
            return {
                "Id": record_id,
                "Notizia__c": "<p>Corpo nuovo</p>",
            }

        with mock.patch.object(scraper.AuraClient, "bootstrap", return_value=None), \
             mock.patch.object(
                 scraper.AuraClient, "get_notizie", return_value=records
             ), \
             mock.patch.object(
                 scraper.AuraClient, "get_notizia_details", side_effect=fake_details
             ):
            doc = scraper.scrape(details=True, workers=1, delay=0)

        self.assertEqual(doc["meta"]["details_ok"], 1)
        self.assertEqual(doc["meta"]["details_failed"], 1)
        self.assertEqual(doc["meta"]["errors_count"], 1)
        self.assertEqual(doc["meta"]["warnings_count"], 0)
        self.assertEqual(len(doc["errors"]), 1)
        self.assertEqual(doc["errors"][0]["scope"], "detail")
        self.assertEqual(doc["errors"][0]["severity"], "error")
        old = next(a for a in doc["articles"] if a["id"] == "a0g_old")
        new = next(a for a in doc["articles"] if a["id"] == "a0g_new")
        self.assertEqual(old["body_source"], "summary")
        self.assertEqual(old["body_text"], "Vecchia")
        self.assertIn("dettaglio non disponibile", old["detail_error"])
        self.assertEqual(new["body_source"], "detail")

    def test_duplicate_ids_are_ignored_with_warning(self):
        record = {
            "Id": "a0g_dup",
            "Name": "SCIOPERO",
            "Titolo__c": "SCIOPERO",
            "Data__c": "2026-11-12",
            "Sintesi1__c": "Sintesi",
        }
        with mock.patch.object(scraper.AuraClient, "bootstrap", return_value=None), \
             mock.patch.object(
                 scraper.AuraClient,
                 "get_notizie",
                 return_value=[record, dict(record)],
             ):
            doc = scraper.scrape(details=False, delay=0)
        self.assertEqual(doc["meta"]["exported_count"], 1)
        self.assertEqual(doc["meta"]["errors_count"], 0)
        self.assertEqual(doc["meta"]["warnings_count"], 1)
        self.assertEqual(doc["errors"][0]["severity"], "warning")
        self.assertIn("duplicato", doc["errors"][0]["message"].lower())

    def test_missing_date_during_since_is_only_a_warning(self):
        records = [
            {
                "Id": "a0g_nodate",
                "Name": "SCIOPERO",
                "Titolo__c": "SCIOPERO",
                "Data__c": None,
                "Sintesi1__c": "Sintesi",
            }
        ]
        with mock.patch.object(scraper.AuraClient, "bootstrap", return_value=None), \
             mock.patch.object(
                 scraper.AuraClient, "get_notizie", return_value=records
             ):
            doc = scraper.scrape(
                details=False,
                since=date(2026, 11, 10),
                delay=0,
            )
        self.assertEqual(doc["meta"]["exported_count"], 1)
        self.assertEqual(doc["meta"]["errors_count"], 0)
        self.assertEqual(doc["meta"]["warnings_count"], 1)
        self.assertEqual(doc["errors"][0]["severity"], "warning")


class OutputTests(unittest.TestCase):
    def test_write_json_atomic(self):
        document = {"meta": {"count": 1}, "articles": [{"id": "x"}], "errors": []}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "out" / "news.json"
            scraper.write_json(document, str(path))
            loaded = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(loaded, document)
            temp_files = list(path.parent.glob(".*.tmp.*"))
            self.assertEqual(temp_files, [])

    def test_write_json_stdout(self):
        document = {"articles": [{"id": "x"}], "errors": []}
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            scraper.write_json(document, "-", compact=True)
        self.assertEqual(json.loads(buffer.getvalue()), document)

    def test_cli_returns_1_on_fatal_error_without_writing(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "news.json"
            with mock.patch.object(
                scraper, "scrape", side_effect=scraper.NetworkError("rete assente")
            ):
                exit_code = scraper.main(["--output", str(path)])
            self.assertEqual(exit_code, 1)
            self.assertFalse(path.exists())

    def test_cli_empty_list_is_partial_unless_allowed(self):
        document = {
            "meta": {
                "source": "ANM",
                "source_legal_name": "ANM S.p.A.",
                "source_url": "x",
                "scraper": "anm_scraper.py",
                "scraper_version": "test",
                "scraped_at": "2026-11-14T00:00:00+01:00",
                "timezone": "Europe/Rome",
                "method": "test",
                "listed_count": 0,
                "exported_count": 0,
                "details_requested": False,
                "details_ok": 0,
                "details_failed": 0,
                "errors_count": 0,
                "duration_seconds": 0,
                "filters": {"since": None, "limit": None},
            },
            "articles": [],
            "errors": [],
        }
        with tempfile.TemporaryDirectory() as directory, mock.patch.object(
            scraper, "scrape", return_value=document
        ):
            path = Path(directory) / "news.json"
            self.assertEqual(scraper.main(["--output", str(path)]), 2)
            self.assertTrue(path.exists())
            self.assertEqual(
                scraper.main(["--allow-empty", "--output", str(path)]), 0
            )

    def test_cli_returns_2_on_partial_errors(self):
        document = {
            "meta": {
                "source": "ANM",
                "source_legal_name": "ANM S.p.A.",
                "source_url": "x",
                "scraper": "anm_scraper.py",
                "scraper_version": "test",
                "scraped_at": "2026-11-14T00:00:00+01:00",
                "timezone": "Europe/Rome",
                "method": "test",
                "listed_count": 1,
                "exported_count": 1,
                "details_requested": False,
                "details_ok": 0,
                "details_failed": 0,
                "errors_count": 1,
                "duration_seconds": 0,
                "filters": {"since": None, "limit": None},
            },
            "articles": [{"id": "x"}],
            "errors": [{"scope": "detail", "message": "boom"}],
        }
        with tempfile.TemporaryDirectory() as directory, \
             mock.patch.object(scraper, "scrape", return_value=document):
            exit_code = scraper.main(
                ["--no-details", "--output", str(Path(directory) / "news.json")]
            )
        self.assertEqual(exit_code, 2)


@unittest.skipUnless(
    os.environ.get("ANM_LIVE_TEST") == "1",
    "imposta ANM_LIVE_TEST=1 per eseguire i test live",
)
class LiveTests(unittest.TestCase):
    def test_live_list(self):
        doc = scraper.scrape(details=False, limit=2, delay=0, timeout=30, retries=2)
        self.assertGreaterEqual(doc["meta"]["listed_count"], 1)
        self.assertGreaterEqual(doc["meta"]["exported_count"], 1)
        article = doc["articles"][0]
        self.assertTrue(article["id"])
        self.assertTrue(article["title"])
        self.assertTrue(article["url"])
        self.assertTrue(article["date"])

    def test_live_detail(self):
        doc = scraper.scrape(
            details=True, limit=1, workers=1, delay=0.1, timeout=30, retries=2
        )
        self.assertEqual(doc["meta"]["details_ok"], 1)
        article = doc["articles"][0]
        self.assertEqual(article["body_source"], "detail")
        self.assertTrue(article["body_text"])
        self.assertTrue(article["body_html"])


if __name__ == "__main__":
    unittest.main()
