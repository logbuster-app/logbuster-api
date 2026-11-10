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
