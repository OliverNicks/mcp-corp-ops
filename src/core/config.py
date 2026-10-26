"""Centralized Application Configuration using Pydantic Settings.

Loads database URLs, Redis parameters, semantic cache similarity thresholds,
LiteLLM proxy credentials, and platform mode flags from environment variables and .env files.
"""

from typing import Literal

from pydantic import AliasChoices, Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # =========================================================================
    # 1. Database Configuration (Dual-Engine: SQLite & MySQL)
    # =========================================================================
    db_engine: Literal["sqlite", "mysql"] = Field(
        default="sqlite",
        validation_alias=AliasChoices("DB_ENGINE"),
        description="Database dialect to use: 'sqlite' for local dev/CI or 'mysql' for Docker/Prod",
    )
    sqlite_path: str = Field(
        default="data/fixtures/best4baby.db",
        validation_alias=AliasChoices("SQLITE_PATH"),
        description="File path to the SQLite database file",
    )
    db_host: str = Field(
        default="localhost",
        validation_alias=AliasChoices("DB_HOST", "MYSQL_HOST"),
        description="MySQL host address or container name",
    )
    db_port: int = Field(
        default=3306,
        validation_alias=AliasChoices("DB_PORT", "MYSQL_PORT"),
        description="MySQL service port",
    )
    db_name: str = Field(
        default="best4baby",
        validation_alias=AliasChoices("DB_NAME", "MYSQL_DATABASE"),
        description="Database name",
    )
    db_user: str = Field(
        default="agent_user",
        validation_alias=AliasChoices("DB_USER", "MYSQL_USER"),
        description="Database username",
    )
    db_password: str = Field(
        default="agent_password",
        validation_alias=AliasChoices("DB_PASSWORD", "MYSQL_PASSWORD"),
        description="Database password",
    )

    @computed_field  # type: ignore[misc]
    @property
    def database_url(self) -> str:
        """Constructs an RFC-compliant SQLAlchemy database URL based on db_engine."""
        if self.db_engine == "sqlite":
            return f"sqlite:///{self.sqlite_path}"
        return (
            f"mysql+pymysql://{self.db_user}:{self.db_password}@"
            f"{self.db_host}:{self.db_port}/{self.db_name}"
        )

    # =========================================================================
    # 2. Redis Stack & Semantic Vector Cache
    # =========================================================================
    redis_host: str = Field(
        default="localhost",
        validation_alias=AliasChoices("REDIS_HOST"),
        description="Redis server host",
    )
    redis_port: int = Field(
        default=6379,
        validation_alias=AliasChoices("REDIS_PORT"),
        description="Redis server port",
    )
    redis_db: int = Field(
        default=0,
        validation_alias=AliasChoices("REDIS_DB"),
        description="Redis logical database index",
    )
    redis_password: str | None = Field(
        default=None,
        validation_alias=AliasChoices("REDIS_PASSWORD"),
        description="Optional Redis password",
    )
    raw_redis_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices("REDIS_URL"),
        description="Direct connection string override for Redis",
    )

    @computed_field  # type: ignore[misc]
    @property
    def redis_url(self) -> str:
        """Constructs the Redis connection URL."""
        if self.raw_redis_url:
            return self.raw_redis_url
        auth = f":{self.redis_password}@" if self.redis_password else ""
        return f"redis://{auth}{self.redis_host}:{self.redis_port}/{self.redis_db}"

    # Semantic Cache Parameters
    similarity_threshold: float = Field(
        default=0.94,
        validation_alias=AliasChoices("CACHE_SIMILARITY_THRESHOLD", "SIMILARITY_THRESHOLD"),
        description="Minimum cosine similarity (0.0 to 1.0) to consider a vector search a cache hit",
    )
    cache_ttl_seconds: int = Field(
        default=86400,
        validation_alias=AliasChoices("CACHE_TTL_SECONDS"),
        description="Time-to-live for cached queries in Redis (default: 24h)",
    )
    embedding_dim: int = Field(
        default=384,
        validation_alias=AliasChoices("EMBEDDING_DIM"),
        description="Dimension of the multilingual MiniLM vector embeddings",
    )
    onnx_model_path: str = Field(
        default="models/embedding_quantized.onnx",
        validation_alias=AliasChoices("ONNX_MODEL_PATH"),
        description="Path to the quantized INT8 ONNX embedding model",
    )
    tokenizer_path: str = Field(
        default="models/tokenizer.json",
        validation_alias=AliasChoices("TOKENIZER_PATH"),
        description="Path to the HuggingFace Rust tokenizer JSON",
    )

    # =========================================================================
    # 3. LiteLLM Proxy Gateway & Failover
    # =========================================================================
    litellm_proxy_url: str = Field(
        default="http://localhost:4000/v1",
        validation_alias=AliasChoices("LITELLM_PROXY_URL"),
        description="Base URL for LiteLLM OpenAI-compatible endpoint",
    )
    litellm_master_key: str = Field(
        default="sk-mcp-corporate-test-key",
        validation_alias=AliasChoices("LITELLM_MASTER_KEY"),
        description="Bearer token for LiteLLM gateway authentication",
    )
    litellm_timeout: float = Field(
        default=5.0,
        validation_alias=AliasChoices("LITELLM_TIMEOUT"),
        description="Client HTTP SLA timeout in seconds (must exceed LiteLLM router 2.5s SLA)",
    )
    litellm_max_connections: int = Field(
        default=100,
        validation_alias=AliasChoices("LITELLM_MAX_CONNECTIONS"),
        description="Maximum concurrent HTTP connections in pool",
    )
    litellm_max_keepalive: int = Field(
        default=20,
        validation_alias=AliasChoices("LITELLM_MAX_KEEPALIVE"),
        description="Maximum idle keep-alive connections preserved",
    )

    # =========================================================================
    # 4. Mode Flags & Transport Protocol
    # =========================================================================
    mock_llm: bool = Field(
        default=False,
        validation_alias=AliasChoices("MOCK_LLM"),
        description="Enable synthetic offline mock completions for CI/CD runs",
    )
    debug: bool = Field(
        default=False,
        validation_alias=AliasChoices("DEBUG"),
        description="Enable verbose debug logging across components",
    )
    mcp_transport: Literal["stdio", "sse"] = Field(
        default="stdio",
        validation_alias=AliasChoices("MCP_TRANSPORT"),
        description="Default transport protocol: 'stdio' for desktop, 'sse' for HTTP/container deployments",
    )
    mcp_host: str = Field(
        default="0.0.0.0",
        validation_alias=AliasChoices("MCP_HOST"),
        description="HTTP host address for SSE transport",
    )
    mcp_port: int = Field(
        default=8000,
        validation_alias=AliasChoices("MCP_PORT", "PORT"),
        description="HTTP port for SSE transport",
    )

    # =========================================================================
    # 5. Observability & Tracing (Langfuse & Prometheus)
    # =========================================================================
    langfuse_host: str = Field(
        default="http://localhost:3000",
        validation_alias=AliasChoices("LANGFUSE_HOST"),
        description="Base URL for the Langfuse tracing server",
    )
    langfuse_public_key: str = Field(
        default="pk-lf-mock",
        validation_alias=AliasChoices("LANGFUSE_PUBLIC_KEY"),
        description="Public API key for Langfuse",
    )
    langfuse_secret_key: str = Field(
        default="sk-lf-mock",
        validation_alias=AliasChoices("LANGFUSE_SECRET_KEY"),
        description="Secret API key for Langfuse",
    )
    metrics_port: int = Field(
        default=8000,
        validation_alias=AliasChoices("METRICS_PORT"),
        description="Port exposed for Prometheus metrics scraping",
    )
    langfuse_enabled: bool = Field(
        default=False,
        validation_alias=AliasChoices("LANGFUSE_ENABLED"),
        description="Send traces to Langfuse (requires real API keys)",
    )


# Singleton instance loaded upon import
settings = Settings()
