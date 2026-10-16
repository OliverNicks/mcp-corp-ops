from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8"
        extra="ignore"
)

    # LiteLLM Gateway
    litellm_proxy_url: str = Field(default="http://localhost:4000/v1")
    litellm_master_key: str = Field(default="sk-mcp-corporate-test-key", validation_alias="LITELLM_MASTER_KEY")
    litellm_timeout: float = Field(
        default=5.0,
        description="Client HTTP timeout in seconds (must exceed LiteLLM router SLA to allow failover)"
    )


settings = Settings()