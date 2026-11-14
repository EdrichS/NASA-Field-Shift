"""App settings, loaded from the repo-root .env.

Secrets are SecretStr, so they show as '**********' if a Settings object is printed or logged.
Variable names match START_TO_FINISH step 9.
"""

from functools import lru_cache
from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    # env_ignore_empty: a blank line like "XAI_BASE_URL=" keeps the default below.
    model_config = SettingsConfigDict(env_file=ENV_FILE, env_ignore_empty=True, extra="ignore")

    # NASA
    earthdata_username: str = ""
    earthdata_password: SecretStr = SecretStr("")
    firms_map_key: SecretStr = SecretStr("")

    # Google Earth Engine
    ee_project: str = ""

    # xAI / Grok
    xai_api_key: SecretStr = SecretStr("")
    xai_base_url: str = "https://api.x.ai/v1"
    xai_model_dev: str = ""
    xai_model_demo: str = ""
    xai_model: str = ""

    # Auth0 (the backend validates tokens)
    auth0_domain: str = ""
    auth0_audience: str = ""

    # TigerData
    database_url: SecretStr = SecretStr("")

    # App: comma-separated list of allowed frontend origins
    frontend_origins: str = "http://localhost:5173"

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.frontend_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
