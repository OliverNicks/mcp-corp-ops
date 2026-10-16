"""
Architectural Purpose

litellm_client.py addresses three core requirements:

Decoupling from Cloud Providers: The MCP server only talks to an OpenAI-compatible endpoint exposed by the LiteLLM proxy 
(http://litellm:4000/v1), shielding the application from provider-specific SDK quirks.

Offline CI/CD & Testing via MOCK_LLM: It supports a mock execution mode (MOCK_LLM=true) that returns synthetic, 
deterministic completions without requiring live API keys or spending cloud credits during automated testing and Locust load runs.

SLA & Resilience Enforcement: It enforces request timeouts (2.5-second SLA) and handles connection retries, allowing LiteLLM's internal 
router to fail over from the primary model (groq/llama-3.3-70b) to the fallback (openai/gpt-4o-mini) seamlessly.
"""

import os
import time
import logging
from typing import Dict, Any, List, Optional
import httpx
from pydantic import BaseModel

logger = logging.getLogger("litellm_client")
logging.basicConfig(level=logging.INFO)

class ChatCompletionResult(BaseModel):
    content: str
    model: str
    latency_ms: float
    simulated: bool = False

class LiteLLMGatewayClient:
    """
    Client interface for interacting with the LiteLLM Proxy gateway.
    Handles fallback propagation, timeouts, and local mock testing.
    """
    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        mock_llm: Optional[bool] = None,
        timeout_seconds: float = 2.5,
    ):
        self.base_url = (base_url or os.getenv("LITELLM_PROXY_URL", "http://localhost:4000/v1")).rstrip("/")
        self.api_key = api_key or os.getenv("LITELLM_MASTER_KEY", "sk-mcp-corporate-test-key")
        
        env_mock = os.getenv("MOCK_LLM", "false").lower() in ("true", "1", "yes")
        self.mock_llm = mock_llm if mock_llm is not None else env_mock
        self.timeout_seconds = timeout_seconds

    def complete(
        self,
        messages: List[Dict[str, str]],
        model: str = "enterprise-agent-llm",
        simulated_delay: float = 0.05,
    ) -> ChatCompletionResult:
        start_time = time.perf_counter()

        # Offline Mock path for CI/CD and zero-token test runs
        if self.mock_llm:
            time.sleep(simulated_delay)
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            return ChatCompletionResult(
                content="SELECT COUNT(*) FROM oc_order;",
                model="mock-agent-llm",
                latency_ms=elapsed_ms,
                simulated=True,
            )

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model,
            "messages": messages,
            "temperature": 0.0,
        }

        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                response = client.post(
                    f"{self.base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()
                
                elapsed_ms = (time.perf_counter() - start_time) * 1000
                content = data["choices"][0]["message"]["content"]
                resolved_model = data.get("model", model)

                return ChatCompletionResult(
                    content=content,
                    model=resolved_model,
                    latency_ms=elapsed_ms,
                    simulated=False,
                )

        except httpx.TimeoutException as exc:
            logger.error("LiteLLM router request timed out (> %.1fs): %s", self.timeout_seconds, exc)
            raise TimeoutError(f"Gateway SLA exceeded ({self.timeout_seconds}s)") from exc
        except httpx.HTTPStatusError as exc:
            logger.error("LiteLLM router responded with error %d: %s", exc.response.status_code, exc.response.text)
            raise RuntimeError(f"Proxy Gateway Error {exc.response.status_code}") from exc
        except httpx.RequestError as exc:
            logger.error("Failed to connect to LiteLLM proxy: %s", exc)
            raise ConnectionError(f"Could not reach LiteLLM proxy at {self.base_url}") from exc