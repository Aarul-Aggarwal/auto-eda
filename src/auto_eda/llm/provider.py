"""LLM provider resolution chain: Anthropic API key -> local Ollama -> none.

Every provider takes a prompt plus a JSON schema and must return a dict
matching that schema, or raise. Callers treat any exception as "fall back
to heuristic ranking".
"""

from __future__ import annotations

import json
import os
from abc import ABC, abstractmethod
from typing import Any

import httpx

from ..config import Config, DEFAULT_CONFIG


class LLMProvider(ABC):
    name: str = "unknown"

    @abstractmethod
    def complete_json(self, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        """Return a dict conforming to `schema`, or raise on any failure."""


class AnthropicProvider(LLMProvider):
    name = "anthropic"

    def __init__(self, config: Config = DEFAULT_CONFIG):
        import anthropic  # deferred so the tool runs without the key configured

        self._client = anthropic.Anthropic()
        self._model = config.anthropic_model

    def complete_json(self, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        response = self._client.messages.create(
            model=self._model,
            max_tokens=4096,
            output_config={"format": {"type": "json_schema", "schema": schema}},
            messages=[{"role": "user", "content": prompt}],
        )
        if response.stop_reason not in ("end_turn", "stop_sequence"):
            raise RuntimeError(f"unexpected stop_reason: {response.stop_reason}")
        text = next(b.text for b in response.content if b.type == "text")
        return json.loads(text)


class OllamaProvider(LLMProvider):
    name = "ollama"

    def __init__(self, config: Config = DEFAULT_CONFIG):
        self._url = config.ollama_url
        self._model = config.ollama_model or self._first_model()

    def _first_model(self) -> str:
        resp = httpx.get(f"{self._url}/api/tags", timeout=3)
        resp.raise_for_status()
        models = resp.json().get("models", [])
        if not models:
            raise RuntimeError("Ollama is running but has no models pulled")
        return models[0]["name"]

    def complete_json(self, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        resp = httpx.post(
            f"{self._url}/api/chat",
            json={
                "model": self._model,
                "messages": [{"role": "user", "content": prompt}],
                "format": schema,  # Ollama constrains output to this JSON schema
                "stream": False,
            },
            timeout=120,
        )
        resp.raise_for_status()
        return json.loads(resp.json()["message"]["content"])


def _ollama_available(config: Config) -> bool:
    try:
        return httpx.get(f"{config.ollama_url}/api/tags", timeout=1.5).status_code == 200
    except httpx.HTTPError:
        return False


def resolve_provider(config: Config = DEFAULT_CONFIG) -> LLMProvider | None:
    """API key -> local Ollama -> None (caller shows the 'no LLM detected' banner)."""
    if os.environ.get("ANTHROPIC_API_KEY"):
        try:
            return AnthropicProvider(config)
        except Exception:
            pass
    if _ollama_available(config):
        try:
            return OllamaProvider(config)
        except Exception:
            pass
    return None
