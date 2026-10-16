"""Centralized Application Configuration using Pydantic Settings."""
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # LiteLLM Proxy Gateway
    litellm_proxy_url: str = Field(
        default="http://localhost:4000/v1",
        validation_alias="LITELLM_PROXY_URL",
        description="Base URL for LiteLLM OpenAI-compatible endpoint",
    )
    litellm_master_key: str = Field(
        default="sk-mcp-corporate-test-key",
        validation_alias="LITELLM_MASTER_KEY",
        description="Bearer token for LiteLLM gateway authentication",
    )
    litellm_timeout: float = Field(
        default=5.0,
        validation_alias="LITELLM_TIMEOUT",
        description="Client HTTP SLA timeout in seconds (must exceed LiteLLM router 2.5s SLA)",
    )
    litellm_max_connections: int = Field(
        default=100,
        validation_alias="LITELLM_MAX_CONNECTIONS",
        description="Maximum concurrent HTTP connections in pool",
    )
    litellm_max_keepalive: int = Field(
        default=20,
        validation_alias="LITELLM_MAX_KEEPALIVE",
        description="Maximum idle keep-alive connections preserved",
    )

    # Offline / CI Testing Mode
    mock_llm: bool = Field(
        default=False,
        validation_alias="MOCK_LLM",
        description="Enable synthetic offline mock completions without API keys",
    )


settings = Settings()