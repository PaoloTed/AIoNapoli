"""Configurable OpenAI-compatible LLM adapter with explicit failure modes.

The adapter never logs credentials and never falls back to a fake answer. A
missing or failed provider is reported as unavailable; callers decide whether a
deterministic path (for the input agent only) is allowed.
"""

from __future__ import annotations

import hashlib
import json
import random
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

import httpx

from app.domain.models.config import AppConfig


class LlmError(RuntimeError):
    """Base class for explicit model failures."""


class LlmUnavailableError(LlmError):
    """The provider is not configured or cannot be reached."""


class LlmTimeoutError(LlmError):
    """The provider did not answer within the configured timeout."""


class LlmRateLimitError(LlmError):
    """The provider asked the client to slow down."""


class LlmInvalidResponseError(LlmError):
    """The provider answered, but not with the declared JSON shape."""


@dataclass(frozen=True)
class LlmResponse:
    text: str
    model: str
    latency_ms: int
    raw: dict[str, Any]


class LlmClient(Protocol):
    model: str

    def complete_json(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        schema_name: str = "response",
    ) -> LlmResponse: ...


def _strip_code_fence(text: str) -> str:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```[a-zA-Z0-9_-]*\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    return cleaned.strip()


def parse_json_content(text: str) -> dict[str, Any]:
    """Parse a model response as one JSON object, tolerating a code fence."""
    cleaned = _strip_code_fence(text)
    try:
        value = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise LlmInvalidResponseError(
            f"risposta modello non JSON: {exc.msg} alla posizione {exc.pos}"
        ) from exc
    if not isinstance(value, dict):
        raise LlmInvalidResponseError("la risposta modello deve essere un oggetto JSON")
    return value


class OpenAICompatibleClient:
    """Minimal chat-completions client for OpenAI-compatible providers."""

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        timeout_s: float = 30.0,
        max_retries: int = 2,
        max_output_tokens: int = 1600,
        temperature: float = 0.0,
        http_client: httpx.Client | None = None,
    ) -> None:
        if not base_url.strip():
            raise LlmUnavailableError("LLM_BASE_URL non configurato")
        if not api_key.strip():
            raise LlmUnavailableError("LLM_API_KEY non configurata")
        if not model.strip():
            raise LlmUnavailableError("LLM_MODEL non configurato")
        self.base_url = base_url.rstrip("/")
        self._api_key = api_key
        self.model = model
        self.timeout_s = float(timeout_s)
        self.max_retries = max(0, int(max_retries))
        self.max_output_tokens = int(max_output_tokens)
        self.temperature = float(temperature)
        self._http_client = http_client
        self._endpoint = (
            self.base_url
            if self.base_url.endswith("/chat/completions")
            else f"{self.base_url}/chat/completions"
        )

    def complete_json(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        schema_name: str = "response",
    ) -> LlmResponse:
        body: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": self.temperature,
            "max_tokens": self.max_output_tokens,
            "response_format": {"type": "json_object"},
        }
        started = time.monotonic()
        response = self._post_with_retry(body)
        latency_ms = int((time.monotonic() - started) * 1000)
        try:
            payload = response.json()
        except ValueError as exc:
            raise LlmInvalidResponseError("risposta provider non JSON") from exc
        if not isinstance(payload, dict):
            raise LlmInvalidResponseError("risposta provider non e' un oggetto")
        choices = payload.get("choices")
        if not isinstance(choices, list) or not choices:
            raise LlmInvalidResponseError("risposta provider senza choices")
        message = choices[0].get("message") if isinstance(choices[0], dict) else None
        content = message.get("content") if isinstance(message, dict) else None
        if not isinstance(content, str) or not content.strip():
            raise LlmInvalidResponseError("risposta provider senza contenuto testuale")
        # Validate and normalize now: callers must never receive an unparsable
        # answer, and a markdown fence is not part of the JSON contract.
        cleaned = _strip_code_fence(content)
        parse_json_content(cleaned)
        return LlmResponse(
            text=cleaned,
            model=str(payload.get("model") or self.model),
            latency_ms=latency_ms,
            raw=payload,
        )

    def _post_with_retry(self, body: dict[str, Any]) -> httpx.Response:
        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                response = self._post(body)
            except httpx.TimeoutException as exc:
                last_error = exc
                if attempt >= self.max_retries:
                    raise LlmTimeoutError(f"timeout provider dopo {self.timeout_s}s") from exc
                self._sleep(attempt)
                continue
            except httpx.RequestError as exc:
                last_error = exc
                if attempt >= self.max_retries:
                    raise LlmUnavailableError(
                        f"provider non raggiungibile: {type(exc).__name__}"
                    ) from exc
                self._sleep(attempt)
                continue

            if response.status_code == 400 and "response_format" in body:
                # Some OpenAI-compatible servers reject response_format. Retry
                # once without it, preserving the JSON-only instruction.
                body.pop("response_format", None)
                continue
            if response.status_code == 429:
                wait = _retry_after_seconds(response.headers.get("Retry-After"))
                if attempt >= self.max_retries:
                    raise LlmRateLimitError(
                        f"provider ha risposto 429 dopo {attempt + 1} tentativi"
                    )
                time.sleep(wait if wait is not None else self._backoff(attempt))
                continue
            if response.status_code in {500, 502, 503, 504}:
                if attempt >= self.max_retries:
                    raise LlmUnavailableError(
                        f"provider HTTP {response.status_code} dopo {attempt + 1} tentativi"
                    )
                self._sleep(attempt, response)
                continue
            if response.status_code >= 400:
                snippet = response.text[:300].replace("\n", " ")
                raise LlmUnavailableError(f"provider HTTP {response.status_code}: {snippet!r}")
            return response
        raise LlmUnavailableError(
            f"provider non disponibile dopo i tentativi: {type(last_error).__name__}"
        )

    def _post(self, body: dict[str, Any]) -> httpx.Response:
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if self._http_client is not None:
            return self._http_client.post(
                self._endpoint, json=body, headers=headers, timeout=self.timeout_s
            )
        with httpx.Client(timeout=self.timeout_s) as client:
            return client.post(self._endpoint, json=body, headers=headers)

    def _backoff(self, attempt: int) -> float:
        return min(30.0, (2**attempt) + random.uniform(0.0, 0.5))

    def _sleep(self, attempt: int, response: httpx.Response | None = None) -> None:
        wait = _retry_after_seconds(response.headers.get("Retry-After")) if response else None
        time.sleep(wait if wait is not None else self._backoff(attempt))


class ReplayLlmClient:
    """Read recorded JSON responses from a directory; never calls the network.

    File names are ``<sha256(system + user + schema)>.json``. The replay mode is
    intentionally separate from live: a missing file is an explicit error.
    """

    def __init__(self, directory: str | Path, *, model: str = "replay") -> None:
        self.directory = Path(directory)
        self.model = model
        if not self.directory.exists():
            raise LlmUnavailableError(f"directory replay LLM assente: {self.directory}")

    @staticmethod
    def key(system_prompt: str, user_prompt: str, schema_name: str) -> str:
        raw = f"{schema_name}\x00{system_prompt}\x00{user_prompt}".encode("utf-8")
        return hashlib.sha256(raw).hexdigest()

    def complete_json(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        schema_name: str = "response",
    ) -> LlmResponse:
        path = self.directory / f"{self.key(system_prompt, user_prompt, schema_name)}.json"
        if not path.exists():
            raise LlmUnavailableError(f"replay LLM non trovato: {path.name}")
        text = path.read_text(encoding="utf-8")
        parse_json_content(text)
        return LlmResponse(text=text, model=self.model, latency_ms=0, raw={})


class DisabledLlmClient:
    """Explicitly unavailable client for ``LLM_MODE=off`` and missing config."""

    model = "disabled"

    def __init__(self, reason: str = "LLM disabilitato dalla configurazione") -> None:
        self.reason = reason

    def complete_json(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        schema_name: str = "response",
    ) -> LlmResponse:
        raise LlmUnavailableError(self.reason)


def _retry_after_seconds(value: str | None) -> float | None:
    if not value:
        return None
    try:
        return max(0.0, float(value.strip()))
    except ValueError:
        return None


def llm_configuration_status(config: AppConfig) -> dict[str, Any]:
    """Describe provider readiness without exposing the API key."""
    configured = bool(config.llm_base_url and config.llm_api_key and config.llm_model)
    reason = None
    if config.llm_mode == "live" and not configured:
        missing = [
            name
            for name, value in (
                ("LLM_BASE_URL", config.llm_base_url),
                ("LLM_API_KEY", config.llm_api_key),
                ("LLM_MODEL", config.llm_model),
            )
            if not value
        ]
        reason = f"variabili mancanti: {', '.join(missing)}"
    if config.llm_mode == "replay" and not config.llm_replay_dir:
        reason = "LLM_REPLAY_DIR non impostata (la cache DB resta comunque usabile)"
    return {
        "mode": config.llm_mode,
        "provider": config.llm_provider,
        "model": config.llm_model or None,
        "base_url_configured": bool(config.llm_base_url),
        "api_key_configured": bool(config.llm_api_key),
        "ready_for_live": configured,
        "reason": reason,
        "prompt_version": config.llm_prompt_version,
        "schema_version": config.llm_schema_version,
    }


def build_llm_client(
    config: AppConfig,
    *,
    http_client: httpx.Client | None = None,
) -> LlmClient:
    """Build the configured client. Missing credentials are never invented."""
    if config.llm_mode == "off":
        return DisabledLlmClient("LLM_MODE=off")
    if config.llm_mode == "mock":
        if not config.llm_replay_dir:
            return DisabledLlmClient("LLM_MODE=mock richiede LLM_REPLAY_DIR")
        return ReplayLlmClient(config.llm_replay_dir, model="mock-replay")
    if config.llm_mode == "replay":
        if config.llm_replay_dir:
            return ReplayLlmClient(config.llm_replay_dir)
        return DisabledLlmClient(
            "LLM_MODE=replay senza LLM_REPLAY_DIR: usare la cache DB o configurare live"
        )
    return OpenAICompatibleClient(
        base_url=config.llm_base_url,
        api_key=config.llm_api_key,
        model=config.llm_model,
        timeout_s=config.llm_timeout_s,
        max_retries=config.llm_max_retries,
        max_output_tokens=config.llm_max_output_tokens,
        temperature=config.llm_temperature,
        http_client=http_client,
    )


__all__ = [
    "DisabledLlmClient",
    "LlmClient",
    "LlmError",
    "LlmInvalidResponseError",
    "LlmRateLimitError",
    "LlmResponse",
    "LlmTimeoutError",
    "LlmUnavailableError",
    "OpenAICompatibleClient",
    "ReplayLlmClient",
    "build_llm_client",
    "llm_configuration_status",
    "parse_json_content",
]
