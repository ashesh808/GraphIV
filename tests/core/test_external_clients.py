"""External credentials and provider options are sent only on model requests."""

import io
import json
import urllib.error

import pytest

from src.core import embed as embedding
from src.core.llm import Gemma


def test_authenticated_completion_omits_router_only_option(monkeypatch, tmp_path):
    observed = {}

    def send(request, timeout):
        observed.update(
            headers=dict(request.header_items()),
            body=json.loads(request.data),
            timeout=timeout,
            url=request.full_url,
        )
        return io.BytesIO(
            json.dumps(
                {"choices": [{"message": {"content": "Grounded answer"}, "finish_reason": "stop"}]}
            ).encode()
        )

    monkeypatch.setattr("urllib.request.urlopen", send)
    model = Gemma(
        "https://model.example/v1",
        "research-model",
        tmp_path,
        api_key="llm-test-key",
        headers={"X-Provider": "custom"},
        timeout=23,
        reasoning_effort=None,
        raise_on_error=True,
    )
    assert model.ask("A question") == "Grounded answer"
    assert observed["url"] == "https://model.example/v1/chat/completions"
    assert observed["headers"]["Authorization"] == "Bearer llm-test-key"
    assert observed["headers"]["X-provider"] == "custom"
    assert observed["timeout"] == 23
    assert "reasoning_effort" not in observed["body"]


def test_legacy_completion_keeps_router_option(monkeypatch, tmp_path):
    def send(request, timeout):
        assert json.loads(request.data)["reasoning_effort"] == "none"
        assert request.get_header("Authorization") is None
        return io.BytesIO(b'{"choices":[{"message":{"content":"answer"}}]}')

    monkeypatch.setattr("urllib.request.urlopen", send)
    assert Gemma("http://localhost:1234/v1", "legacy", tmp_path).ask("Question") == "answer"


def test_external_auth_failure_is_legible_without_credential(monkeypatch, tmp_path):
    def denied(request, timeout):
        raise urllib.error.HTTPError(request.full_url, 401, "Unauthorized", None, None)

    monkeypatch.setattr("urllib.request.urlopen", denied)
    with pytest.raises(RuntimeError, match="LLM service returned HTTP 401") as error:
        Gemma(
            "https://model.example/v1",
            "model",
            tmp_path,
            api_key="do-not-leak",
            raise_on_error=True,
        ).ask("Question")
    assert "do-not-leak" not in str(error.value)
    assert not list(tmp_path.glob("*.txt"))


def test_credentials_are_never_sent_to_plain_http_external_services(tmp_path):
    with pytest.raises(ValueError, match="require HTTPS"):
        Gemma("http://remote.example/v1", "model", tmp_path, api_key="private-key")
    with pytest.raises(ValueError, match="require HTTPS"):
        embedding.embed("http://remote.example/v1", "model", "question", api_key="private-key")


@pytest.mark.parametrize(
    "base",
    ["https://embed.example", "https://embed.example/v1", "https://embed.example/v1/embeddings"],
)
def test_embedding_credentials_endpoint_and_normalization(monkeypatch, base):
    def send(request, timeout):
        assert request.full_url == "https://embed.example/v1/embeddings"
        assert request.get_header("Authorization") == "Bearer embed-test-key"
        assert json.loads(request.data)["input"] == ["search_query: citation graphs"]
        assert timeout == 17
        return io.BytesIO(b'{"data":[{"embedding":[3,4]}]}')

    monkeypatch.setattr("urllib.request.urlopen", send)
    assert embedding.embed(
        base, "model", "citation graphs", api_key="embed-test-key", timeout=17
    ) == [0.6, 0.8]
