"""
LiteLLM Gateway Client with AsyncIO, Connection Pooling, and Pydantic Settings.
Designed for high-throughput, non-blocking tool execution in FastMCP.
"""

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional
import httpx
from pydantic import BaseModel, Field

from src.core.config import Settings, settings as app_settings

logger = logging.getLogger("litellm_client")


class TokenUsage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class ChatCompletionResult(BaseModel):
    content: str
    model: str
    latency_ms: float
    usage: TokenUsage = Field(default_factory=TokenUsage)
    simulated: bool = False


class LiteLLMGatewayClient:
    """
    Asynchronous client for the LiteLLM Proxy Gateway.

    Key Features:
    - Automatically configured from Pydantic Settings (src/core/config.py)
    - Reusable connection pooling via httpx.AsyncClient (no per-request TCP handshakes)
    - Native asyncio non-blocking I/O (prevents freezing the FastMCP event loop)
    - SLA timeout handling with failover window support (5.0s client timeout vs 2.5s provider SLA)
    - Offline MOCK_LLM mode with simulated latency for CI testing
    """

    def __init__(
        self,
        config: Optional[Settings] = None,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout: Optional[float] = None,
        mock_llm: Optional[bool] = None,
    ):
        cfg = config or app_settings

        raw_url = (base_url or cfg.litellm_proxy_url).rstrip("/")
        self.base_url = raw_url if raw_url.endswith("/v1") else f"{raw_url}/v1"
        self.api_key = api_key or cfg.litellm_master_key
        self.timeout = timeout or cfg.litellm_timeout
        self.mock_llm = mock_llm if mock_llm is not None else cfg.mock_llm

        # Persistent connection pool limits
        self._limits = httpx.Limits(
            max_connections=cfg.litellm_max_connections,
            max_keepalive_connections=cfg.litellm_max_keepalive,
            keepalive_expiry=30.0,
        )

        self._headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        # Lazy async client instance
        self._client: Optional[httpx.AsyncClient] = None

    def _get_client(self) -> httpx.AsyncClient:
        """Get or initialize the shared async client pool."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout),
                limits=self._limits,
                headers=self._headers,
            )
        return self._client

    async def acomplete(
        self,
        messages: List[Dict[str, str]],
        model: str = "enterprise-agent-llm",
        simulated_delay: float = 0.05,
    ) -> ChatCompletionResult:
        """
        Asynchronously sends a chat completion request to the LiteLLM proxy.
        Yields control back to the asyncio event loop while waiting for response.
        """
        start_time = time.perf_counter()

        # Offline Mock Mode (CI / Unit Tests)
        if self.mock_llm:
            await asyncio.sleep(simulated_delay)
            return self._build_mock_response(messages, start_time)

        payload = {
            "model": model,
            "messages": messages,
            "temperature": 0.0,
        }

        try:
            client = self._get_client()
            response = await client.post(
                f"{self.base_url}/chat/completions",
                json=payload,
            )
            response.raise_for_status()
            return self._parse_response(response.json(), model, start_time)

        except httpx.TimeoutException as exc:
            logger.error("LiteLLM request timed out (> %.1fs): %s", self.timeout, exc)
            raise TimeoutError(f"Gateway SLA exceeded ({self.timeout}s)") from exc
        except httpx.HTTPStatusError as exc:
            logger.error("LiteLLM returned HTTP %d: %s", exc.response.status_code, exc.response.text)
            raise RuntimeError(f"LiteLLM Gateway HTTP Error {exc.response.status_code}") from exc
        except httpx.RequestError as exc:
            logger.error("Network error reaching LiteLLM at %s: %s", self.base_url, exc)
            raise ConnectionError(f"Could not reach LiteLLM gateway at {self.base_url}") from exc

    def _parse_response(
        self,
        data: Dict[str, Any],
        requested_model: str,
        start_time: float,
    ) -> ChatCompletionResult:
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        content = data["choices"][0]["message"]["content"]
        resolved_model = data.get("model", requested_model)
        raw_usage = data.get("usage", {})

        return ChatCompletionResult(
            content=content,
            model=resolved_model,
            latency_ms=elapsed_ms,
            usage=TokenUsage(
                prompt_tokens=raw_usage.get("prompt_tokens", 0),
                completion_tokens=raw_usage.get("completion_tokens", 0),
                total_tokens=raw_usage.get("total_tokens", 0),
            ),
            simulated=False,
        )

    def _build_mock_response(
        self,
        messages: List[Dict[str, str]],
        start_time: float,
    ) -> ChatCompletionResult:
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        user_query = " ".join([m.get("content", "") for m in messages]).lower()

        if "stock" in user_query or "product" in user_query:
            sql = "SELECT product_id, model, quantity, price FROM oc_product WHERE status = 1 LIMIT 100;"
        elif "sales" in user_query or "revenue" in user_query or "order" in user_query:
            sql = "SELECT COUNT(order_id) AS total_orders, SUM(total) AS gross_revenue FROM oc_order LIMIT 100;"
        else:
            sql = "SELECT product_id, model, quantity FROM oc_product LIMIT 100;"

        return ChatCompletionResult(
            content=sql,
            model="mock-agent-llm",
            latency_ms=elapsed_ms,
            usage=TokenUsage(prompt_tokens=25, completion_tokens=15, total_tokens=40),
            simulated=True,
        )

    # -------------------------------------------------------------------------
    # Lifecycle Management
    # -------------------------------------------------------------------------
    async def aclose(self) -> None:
        """Close the underlying connection pool."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def __aenter__(self) -> "LiteLLMGatewayClient":
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.aclose()