"""Provider-agnostic LLM gateway with a runtime switch between Gemini and Azure AI Foundry.

Agents never call an SDK directly. They call ``llm.complete_json`` and always receive either
a parsed result or ``None`` plus call metadata, so every agent can fall back to its
deterministic rule output when a provider is unavailable or slow.
"""
from __future__ import annotations

import json
import logging
import re
import threading
import time
from dataclasses import asdict, dataclass

from app.config import settings

log = logging.getLogger("arro.llm")

PROVIDERS = ("gemini", "azure")


@dataclass
class LLMCall:
    provider: str
    model: str
    ok: bool
    latency_ms: int
    purpose: str
    error: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


class LLMGateway:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._gemini_client = None
        self._azure_client = None
        preferred = settings.llm_provider if settings.llm_provider in PROVIDERS else "azure"
        if not self.is_configured(preferred):
            preferred = next((p for p in PROVIDERS if self.is_configured(p)), preferred)
        self._active = preferred

    # ---- configuration ---------------------------------------------------
    def is_configured(self, provider: str) -> bool:
        if provider == "gemini":
            return bool(settings.gemini_api_key)
        if provider == "azure":
            return bool(settings.azure_api_key and settings.azure_endpoint)
        return False

    def model_for(self, provider: str) -> str:
        return settings.gemini_model if provider == "gemini" else settings.azure_deployment

    @property
    def active(self) -> str:
        return self._active

    def set_active(self, provider: str) -> None:
        if provider not in PROVIDERS:
            raise ValueError(f"Unknown provider '{provider}'")
        if not self.is_configured(provider):
            raise ValueError(f"Provider '{provider}' has no API key configured")
        with self._lock:
            self._active = provider

    def status(self) -> dict:
        return {
            "active": self._active,
            "providers": [
                {"id": "gemini", "label": "Google Gemini", "model": settings.gemini_model,
                 "configured": self.is_configured("gemini")},
                {"id": "azure", "label": "Azure AI Foundry", "model": settings.azure_deployment,
                 "configured": self.is_configured("azure")},
            ],
        }

    # ---- clients ---------------------------------------------------------
    def _gemini(self):
        if self._gemini_client is None:
            from google import genai
            from google.genai import types

            self._gemini_client = genai.Client(
                api_key=settings.gemini_api_key,
                http_options=types.HttpOptions(timeout=int(settings.llm_timeout_s * 1000)),
            )
        return self._gemini_client

    def _azure(self):
        if self._azure_client is None:
            from openai import OpenAI

            self._azure_client = OpenAI(
                base_url=settings.azure_endpoint,
                api_key=settings.azure_api_key,
                timeout=settings.llm_timeout_s,
                max_retries=1,
            )
        return self._azure_client

    # ---- calls -----------------------------------------------------------
    def complete(self, system: str, prompt: str, *, purpose: str, json_mode: bool = False,
                 provider: str | None = None) -> tuple[str | None, LLMCall]:
        provider = provider or self._active
        model = self.model_for(provider)
        started = time.perf_counter()
        if not self.is_configured(provider):
            return None, LLMCall(provider, model, False, 0, purpose, "Provider not configured")
        try:
            if provider == "gemini":
                from google.genai import types

                resp = self._gemini().models.generate_content(
                    model=model,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=system,
                        temperature=0.3,
                        response_mime_type="application/json" if json_mode else None,
                    ),
                )
                text = resp.text
            else:
                resp = self._azure().responses.create(model=model, instructions=system, input=prompt)
                text = resp.output_text
            latency = int((time.perf_counter() - started) * 1000)
            return text, LLMCall(provider, model, True, latency, purpose)
        except Exception as exc:  # noqa: BLE001 - surface any provider failure as metadata
            latency = int((time.perf_counter() - started) * 1000)
            log.warning("LLM call failed (%s/%s): %s", provider, purpose, exc)
            return None, LLMCall(provider, model, False, latency, purpose, str(exc)[:240])

    def complete_json(self, system: str, prompt: str, *, purpose: str) -> tuple[dict | None, LLMCall]:
        text, call = self.complete(
            system + "\nRespond with a single valid JSON object only. No markdown fences.",
            prompt, purpose=purpose, json_mode=True,
        )
        if text is None:
            return None, call
        parsed = parse_json(text)
        if parsed is None:
            call.ok = False
            call.error = "Model returned unparseable JSON"
        return parsed, call


def parse_json(text: str) -> dict | None:
    cleaned = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.MULTILINE).strip()
    try:
        value = json.loads(cleaned)
        return value if isinstance(value, dict) else {"items": value}
    except json.JSONDecodeError:
        pass
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start != -1 and end > start:
        try:
            return json.loads(cleaned[start:end + 1])
        except json.JSONDecodeError:
            return None
    return None


llm = LLMGateway()
