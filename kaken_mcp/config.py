"""Configuration management for KAKEN MCP."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_prefix="KAKEN_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # CiNii API Application ID (required)
    app_id: str

    # API endpoints
    project_api_url: str = "https://kaken.nii.ac.jp/opensearch/"
    researcher_api_url: str = "https://nrid.nii.ac.jp/opensearch/"

    # Default request settings
    default_limit: int = 20
    max_limit: int = 200
    request_timeout: float = 30.0


def get_settings() -> Settings:
    """Get application settings."""
    return Settings()  # type: ignore[call-arg]
