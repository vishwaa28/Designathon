from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# Trust the operating system certificate store (corporate proxies re-sign TLS traffic with a private root CA
# that certifi does not know). Verification stays on; this only changes which roots are trusted.
try:
    import truststore

    truststore.inject_into_ssl()
except Exception:  # noqa: BLE001 - optional dependency, fall back to the default bundle
    pass

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

    # E-mail: Twilio SendGrid (API key) or plain SMTP. EMAIL_PROVIDER=sendgrid|smtp, else SendGrid when its key is set.
    email_provider = (_env("EMAIL_PROVIDER", default="") or "").lower()
    sendgrid_api_key = _env("SENDGRID_API_KEY")
    sendgrid_from = _env("SENDGRID_FROM", "SENDGRID_FROM_EMAIL")
    sendgrid_from_name = _env("SENDGRID_FROM_NAME", default="Meridian Airways Disruption Desk")

    smtp_host = _env("SMTP_HOST")
    smtp_port = int(_env("SMTP_PORT", default="587"))
    smtp_user = _env("SMTP_USER", "SMTP_USERNAME")
    smtp_password = _env("SMTP_PASSWORD")
    smtp_from = _env("SMTP_FROM", default=smtp_user)
    smtp_from_name = _env("SMTP_FROM_NAME", default="Meridian Airways Disruption Desk")

    sms_provider = (_env("SMS_PROVIDER", default="") or "").lower()
    twilio_account_sid = _env("TWILIO_ACCOUNT_SID")
    twilio_auth_token = _env("TWILIO_AUTH_TOKEN")
    twilio_from = _env("TWILIO_FROM", "TWILIO_PHONE_NUMBER")
    twilio_messaging_service_sid = _env("TWILIO_MESSAGING_SERVICE_SID")
    fast2sms_api_key = _env("FAST2SMS_API_KEY")

    # SQLite (stdlib). Vercel's filesystem is read-only except /tmp, so the file lives there when deployed.
    database_path = _env("DATABASE_PATH") or (
        "/tmp/arro.db" if os.getenv("VERCEL") else str(SERVER_DIR / "data" / "arro.db"))

    # AviationStack real-time flights. The free plan allows ~100 calls a month, so results are cached in SQLite.
    aviationstack_key = _env("AVIATIONSTACK_API_KEY", "AVIATION_STACK_API", "aviation_stack_api", "AVIATIONSTACK_ACCESS_KEY")
    aviationstack_base = (_env("AVIATIONSTACK_BASE_URL", default="https://api.aviationstack.com/v1") or "").rstrip("/")
    aviationstack_cache_s = int(_env("AVIATIONSTACK_CACHE_SECONDS", default="900"))
    aviationstack_airport = (_env("AVIATIONSTACK_AIRPORT", default="MAA") or "MAA").upper()

    # Crowd monitor: how often the browser sends a camera frame to the vision model
    crowd_frame_interval_s = int(_env("CROWD_FRAME_INTERVAL_SECONDS", default="20"))

    agent_step_delay_s = float(_env("AGENT_STEP_DELAY_SECONDS", default="0.8"))
    weather_api_enabled = (_env("WEATHER_API_ENABLED", default="true") or "true").lower() == "true"
    telemetry_interval_s = float(_env("TELEMETRY_INTERVAL_SECONDS", default="6"))
    cors_origins = [o.strip() for o in (_env("CORS_ORIGINS", default="http://localhost:5173,http://127.0.0.1:5173") or "").split(",") if o.strip()]


settings = Settings()
