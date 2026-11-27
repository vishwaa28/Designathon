from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

SERVER_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = SERVER_DIR.parent

load_dotenv(REPO_ROOT / ".env")
load_dotenv(SERVER_DIR / ".env")


def _env(*names: str, default: str | None = None) -> str | None:
    for name in names:
        value = os.getenv(name)
        if value:
            return value.strip()
    return default


class Settings:
    app_name = "ARRO Disruption Recovery Orchestrator"
    version = "1.0.0"

    llm_provider = (_env("LLM_PROVIDER", default="azure") or "azure").lower()
    llm_timeout_s = float(_env("LLM_TIMEOUT_SECONDS", default="45"))

    gemini_api_key = _env("GEMINI_API_KEY", "gemini_api_key", "GOOGLE_API_KEY")
    gemini_model = _env("GEMINI_MODEL", default="gemini-2.5-flash")

    azure_endpoint = _env("AZURE_FOUNDRY_ENDPOINT", "azure_endpoint")
    azure_api_key = _env("AZURE_FOUNDRY_API_KEY", "AZURE_API_KEY", "azure_api_key")
    azure_deployment = _env("AZURE_FOUNDRY_DEPLOYMENT", "azure_deployment", default="gpt-5.4")

    voice_endpoint = _env("AZURE_VOICELIVE_ENDPOINT", default=azure_endpoint)
    voice_api_key = _env("AZURE_VOICELIVE_API_KEY", "AZURE_FOUNDRY_API_KEY", "AZURE_API_KEY", "azure_api_key")
    voice_model = _env("AZURE_VOICELIVE_MODEL", default="gpt-4.1")
    voice_api_version = _env("AZURE_VOICELIVE_API_VERSION", default="2025-10-01")

    voice_audio_processing = (_env("AZURE_VOICELIVE_AUDIO_PROCESSING", default="true") or "true").lower() == "true"

    agent_step_delay_s = float(_env("AGENT_STEP_DELAY_SECONDS", default="0.8"))
    weather_api_enabled = (_env("WEATHER_API_ENABLED", default="true") or "true").lower() == "true"
    telemetry_interval_s = float(_env("TELEMETRY_INTERVAL_SECONDS", default="6"))
    cors_origins = [o.strip() for o in (_env("CORS_ORIGINS", default="http://localhost:5173,http://127.0.0.1:5173") or "").split(",") if o.strip()]


settings = Settings()
