"""Transport-level tests for the configurable LLM adapter (no real provider)."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from app.services.llm.client import (
    LlmInvalidResponseError,
    LlmRateLimitError,
    LlmUnavailableError,
    OpenAICompatibleClient,
    ReplayLlmClient,
)


def _client(handler: object, *, retries: int = 0) -> OpenAICompatibleClient:
    return OpenAICompatibleClient(
        base_url="https://llm.test/v1",
        api_key="not-a-real-key",
        model="small-test-model",
        timeout_s=2,
        max_retries=retries,
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),  # type: ignore[arg-type]
    )


def test_valid_json_response_is_parsed() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == "Bearer not-a-real-key"
        return httpx.Response(
            200,
            json={
                "model": "small-test-model",
                "choices": [{"message": {"content": '{"relevant": true}'}}],
            },
            request=request,
        )

    response = _client(handler).complete_json("system", "user")
    assert json.loads(response.text) == {"relevant": True}
    assert response.model == "small-test-model"


def test_code_fence_is_tolerated() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": '```json\n{"relevant": false}\n```'}}]},
            request=request,
        )

    response = _client(handler).complete_json("system", "user")
    assert json.loads(response.text) == {"relevant": False}


def test_non_json_answer_is_rejected() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "not json"}}]},
            request=request,
        )

    with pytest.raises(LlmInvalidResponseError):
        _client(handler).complete_json("system", "user")


def test_rate_limit_is_explicit() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, headers={"Retry-After": "1"}, request=request)

    with pytest.raises(LlmRateLimitError):
        _client(handler).complete_json("system", "user")


def test_server_error_is_unavailable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="down", request=request)

    with pytest.raises(LlmUnavailableError):
        _client(handler).complete_json("system", "user")


def test_missing_credentials_are_not_invented() -> None:
    with pytest.raises(LlmUnavailableError):
        OpenAICompatibleClient(base_url="https://llm.test/v1", api_key="", model="m")


def test_replay_reads_only_a_recorded_file(tmp_path: Path) -> None:
    client = ReplayLlmClient(tmp_path)
    with pytest.raises(LlmUnavailableError):
        client.complete_json("system", "user")
    key = ReplayLlmClient.key("system", "user", "response")
    (tmp_path / f"{key}.json").write_text('{"ok": true}', encoding="utf-8")
    response = client.complete_json("system", "user")
    assert json.loads(response.text) == {"ok": True}
