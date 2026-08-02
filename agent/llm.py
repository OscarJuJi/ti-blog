"""The language model backends, spoken to over plain HTTP.

Two of them: Gemini, which is what the scheduled job uses, and Ollama, which is
what you use locally to iterate on the prompt without spending quota. Both
expose one method, so the rest of the agent never learns which it got.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from typing import Any, Protocol

GEMINI_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/interactions"
OLLAMA_HOST = "http://localhost:11434"

RETRIES = 3
RETRY_STATUSES = frozenset({408, 429, 500, 502, 503, 504})


class LLMError(RuntimeError):
    """Raised when a model cannot be reached, or answers with nothing usable."""


class LLM(Protocol):
    name: str

    def generate(self, prompt: str, *, system: str = "") -> str: ...


class Gemini:
    """https://ai.google.dev/gemini-api/docs/quickstart"""

    def __init__(
        self,
        model: str,
        api_key: str,
        *,
        endpoint: str = GEMINI_ENDPOINT,
        timeout: int = 90,
        max_output_tokens: int = 4096,
        temperature: float = 0.4,
    ):
        if not api_key:
            raise LLMError("no Gemini API key; set GEMINI_API_KEY")
        self.name = f"gemini:{model}"
        self._model = model
        self._key = api_key
        self._endpoint = endpoint
        self._timeout = timeout
        self._max_output_tokens = max_output_tokens
        self._temperature = temperature

    def generate(self, prompt: str, *, system: str = "") -> str:
        body: dict[str, Any] = {
            "model": self._model,
            "input": prompt,
            "generation_config": {
                "temperature": self._temperature,
                "max_output_tokens": self._max_output_tokens,
            },
        }
        if system:
            body["system_instruction"] = system

        payload = _post(
            self._endpoint,
            body,
            headers={"x-goog-api-key": self._key},
            timeout=self._timeout,
        )
        text = _gemini_text(payload)
        if not text:
            raise LLMError(f"Gemini returned no text: {json.dumps(payload)[:400]}")
        return text


class Ollama:
    """A local model, for developing the prompt without touching the quota."""

    def __init__(
        self,
        model: str,
        *,
        host: str = OLLAMA_HOST,
        timeout: int = 300,
        temperature: float = 0.4,
    ):
        self.name = f"ollama:{model}"
        self._model = model
        self._url = f"{host.rstrip('/')}/api/generate"
        self._timeout = timeout
        self._temperature = temperature

    def generate(self, prompt: str, *, system: str = "") -> str:
        body: dict[str, Any] = {
            "model": self._model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": self._temperature},
        }
        if system:
            body["system"] = system

        payload = _post(self._url, body, headers={}, timeout=self._timeout)
        text = str(payload.get("response", "")).strip()
        if not text:
            raise LLMError(f"Ollama returned no text: {json.dumps(payload)[:400]}")
        return text


def from_environment(
    *, backend: str = "auto", model: str = "", ollama_model: str = "qwen3:8b"
) -> LLM:
    """Pick a backend: an explicit one, or whichever the environment can serve."""
    key = os.environ.get("GEMINI_API_KEY", "").strip()

    if backend == "gemini" or (backend == "auto" and key):
        return Gemini(model, key)
    if backend in ("ollama", "auto"):
        return Ollama(ollama_model)
    raise LLMError(f"unknown backend: {backend!r}")


def _gemini_text(payload: dict[str, Any]) -> str:
    """Pull the answer out of an interaction, whichever shape it arrives in."""
    if isinstance(payload.get("output_text"), str):
        return payload["output_text"].strip()

    for step in reversed(payload.get("steps") or []):
        blocks = step.get("content") or []
        text = "".join(
            block.get("text", "")
            for block in blocks
            if isinstance(block, dict) and block.get("type", "text") == "text"
        ).strip()
        if text:
            return text

    # The older generateContent shape, in case the endpoint is pointed back at it.
    for candidate in payload.get("candidates") or []:
        parts = (candidate.get("content") or {}).get("parts") or []
        text = "".join(part.get("text", "") for part in parts).strip()
        if text:
            return text

    return ""


def _post(
    url: str, body: dict[str, Any], *, headers: dict[str, str], timeout: int
) -> dict[str, Any]:
    """POST JSON, retrying the failures that tend to pass on their own."""
    request_headers = {"Content-Type": "application/json", **headers}
    data = json.dumps(body).encode("utf-8")
    last: Exception | None = None

    for attempt in range(1, RETRIES + 1):
        request = urllib.request.Request(url, data=data, headers=request_headers)
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            detail = error.read().decode("utf-8", "replace")[:300]
            last = LLMError(f"HTTP {error.code} from {url}: {detail}")
            if error.code not in RETRY_STATUSES:
                raise last from error
        except urllib.error.URLError as error:
            last = LLMError(f"could not reach {url}: {error.reason}")
        except json.JSONDecodeError as error:
            raise LLMError(f"{url} did not answer with JSON: {error}") from error

        if attempt < RETRIES:
            time.sleep(2**attempt)

    raise last or LLMError(f"{url} failed for reasons unknown")
