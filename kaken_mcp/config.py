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

    # Base URLs for KAKEN website
    base_url: str = "https://kaken.nii.ac.jp"
    researcher_base_url: str = "https://nrid.nii.ac.jp"

    # Default request settings
    default_limit: int = 20
    max_limit: int = 200
    request_timeout: float = 30.0

    # User agent for requests
    user_agent: str = "KAKEN-MCP/0.1.0 (https://github.com/leaveanest/kaken-mcp)"


def get_settings() -> Settings:
    """Get application settings."""
    return Settings()
