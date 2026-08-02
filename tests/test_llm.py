import io
import json
import urllib.error

import pytest

from agent import llm


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


def responder(*outcomes):
    """Answer each call with the next outcome, raising the ones that are errors."""
    remaining = list(outcomes)
    calls = []

    def urlopen(request, timeout=None):
        calls.append(request)
        outcome = remaining.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return FakeResponse(json.dumps(outcome).encode("utf-8"))

    urlopen.calls = calls
    return urlopen


def http_error(code, body=b"nope"):
    return urllib.error.HTTPError("https://x", code, "err", {}, io.BytesIO(body))


@pytest.fixture(autouse=True)
def no_waiting(monkeypatch):
    monkeypatch.setattr(llm.time, "sleep", lambda _: None)


def test_reads_the_text_out_of_an_interaction(monkeypatch):
    payload = {
        "status": "completed",
        "steps": [{"type": "model_output", "content": [{"type": "text", "text": "Hello."}]}],
    }
    monkeypatch.setattr("urllib.request.urlopen", responder(payload))

    assert llm.Gemini("gemini-3.6-flash", "key").generate("hi") == "Hello."


def test_reads_the_output_text_shortcut_when_it_is_there(monkeypatch):
    monkeypatch.setattr("urllib.request.urlopen", responder({"output_text": " Hi "}))
    assert llm.Gemini("m", "key").generate("hi") == "Hi"


def test_reads_the_older_generate_content_shape(monkeypatch):
    payload = {"candidates": [{"content": {"parts": [{"text": "Legacy."}]}}]}
    monkeypatch.setattr("urllib.request.urlopen", responder(payload))
    assert llm.Gemini("m", "key").generate("hi") == "Legacy."


def test_an_answer_with_no_text_is_an_error(monkeypatch):
    monkeypatch.setattr("urllib.request.urlopen", responder({"steps": []}))
    with pytest.raises(llm.LLMError, match="no text"):
        llm.Gemini("m", "key").generate("hi")


def test_sends_the_key_the_model_and_the_system_instruction(monkeypatch):
    urlopen = responder({"output_text": "ok"})
    monkeypatch.setattr("urllib.request.urlopen", urlopen)

    llm.Gemini("gemini-3.6-flash", "secret").generate("the prompt", system="be brief")

    request = urlopen.calls[0]
    body = json.loads(request.data)
    assert request.get_header("X-goog-api-key") == "secret"
    assert body["model"] == "gemini-3.6-flash"
    assert body["input"] == "the prompt"
    assert body["system_instruction"] == "be brief"


def test_retries_a_rate_limit_and_then_succeeds(monkeypatch):
    urlopen = responder(http_error(429), {"output_text": "second time lucky"})
    monkeypatch.setattr("urllib.request.urlopen", urlopen)

    assert llm.Gemini("m", "key").generate("hi") == "second time lucky"
    assert len(urlopen.calls) == 2


def test_gives_up_after_the_last_retry(monkeypatch):
    urlopen = responder(*[http_error(503)] * llm.RETRIES)
    monkeypatch.setattr("urllib.request.urlopen", urlopen)

    with pytest.raises(llm.LLMError, match="HTTP 503"):
        llm.Gemini("m", "key").generate("hi")
    assert len(urlopen.calls) == llm.RETRIES


def test_does_not_retry_a_bad_request(monkeypatch):
    urlopen = responder(http_error(400, b"bad model"))
    monkeypatch.setattr("urllib.request.urlopen", urlopen)

    with pytest.raises(llm.LLMError, match="bad model"):
        llm.Gemini("m", "key").generate("hi")
    assert len(urlopen.calls) == 1


def test_a_missing_key_is_refused_up_front():
    with pytest.raises(llm.LLMError, match="GEMINI_API_KEY"):
        llm.Gemini("m", "")


def test_ollama_speaks_its_own_shape(monkeypatch):
    urlopen = responder({"response": "  local answer  "})
    monkeypatch.setattr("urllib.request.urlopen", urlopen)

    assert llm.Ollama("qwen3:8b").generate("hi", system="s") == "local answer"

    body = json.loads(urlopen.calls[0].data)
    assert body == {
        "model": "qwen3:8b",
        "prompt": "hi",
        "stream": False,
        "options": {"temperature": 0.4},
        "system": "s",
    }


def test_the_backend_follows_the_environment(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "key")
    assert llm.from_environment(model="m").name == "gemini:m"

    monkeypatch.delenv("GEMINI_API_KEY")
    assert llm.from_environment(model="m", ollama_model="qwen3:8b").name == "ollama:qwen3:8b"


def test_asking_for_gemini_without_a_key_is_an_error(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(llm.LLMError):
        llm.from_environment(backend="gemini", model="m")
