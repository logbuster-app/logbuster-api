"""Configuração por ambiente; carregar a aplicação não abre conexões."""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).with_name(".env"), override=False)


class Settings:
    @property
    def omdb_api_key(self) -> str:
        return os.getenv("OMDB_API_KEY", "")

    @property
    def omdb_base_url(self) -> str:
        return os.getenv("OMDB_BASE_URL", "https://www.omdbapi.com")

    @property
    def jwt_secret(self) -> str:
        return os.getenv("JWT_SECRET", "")

    @property
    def jwt_expires_in(self) -> int:
        return int(os.getenv("JWT_EXPIRES_IN", "3600"))

    # IA (SPEC-BACK-09): qualquer provedor com API compatível com
    # `POST {AI_BASE_URL}/chat/completions`. Sem chave, URL ou modelo, os
    # recursos de IA respondem `unavailable` sem quebrar o restante da API.
    @property
    def ai_base_url(self) -> str:
        return os.getenv("AI_BASE_URL", "").rstrip("/")

    @property
    def ai_api_key(self) -> str:
        return os.getenv("AI_API_KEY", "")

    @property
    def ai_model(self) -> str:
        return os.getenv("AI_MODEL", "")

    @property
    def ai_reasoning_effort(self) -> str:
        return os.getenv("AI_REASONING_EFFORT", "").strip()

    @property
    def ai_timeout_seconds(self) -> float:
        return float(os.getenv("AI_TIMEOUT_SECONDS", "15"))

    @property
    def ai_spoiler_timeout_seconds(self) -> float:
        return float(os.getenv("AI_SPOILER_TIMEOUT_SECONDS", "6"))

    @property
    def ai_retry_after_seconds(self) -> int:
        return int(os.getenv("AI_RETRY_AFTER_SECONDS", "60"))

    @property
    def review_summary_regen_threshold(self) -> int:
        return max(1, int(os.getenv("REVIEW_SUMMARY_REGEN_THRESHOLD", "3")))

    @property
    def app_env(self) -> str:
        return os.getenv("APP_ENV", "development")

    @property
    def log_level(self) -> str:
        return os.getenv("LOG_LEVEL", "INFO").upper()

    @property
    def cors_allowed_origins(self) -> list[str]:
        default = (
            "http://localhost:3000,http://localhost:5173"
            if self.app_env == "development"
            else ""
        )
        return [
            origin.strip()
            for origin in os.getenv(
                "CORS_ALLOWED_ORIGINS", os.getenv("CORS_ORIGINS", default)
            ).split(",")
            if origin.strip()
        ]


settings = Settings()
