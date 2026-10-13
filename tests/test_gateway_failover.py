import os
import pytest
from src.gateway.litellm_client import LiteLLMGatewayClient

def test_mock_profile_completion():
    client = LiteLLMGatewayClient(
        base_url="http://localhost:4000/v1",
        api_key="sk-mcp-corporate-test-key",
        mock_llm=True,
    )
    result = client.complete(
        messages=[{"role": "user", "content": "How many orders were placed today?"}]
    )
    assert result.content is not None
    assert result.latency_ms < 2500  # Within the 2.5s SLA
    assert result.simulated is True

def test_gateway_timeout_enforcement():
    # Setting an ultra-short timeout (1ms) to verify SLA error propagation
    client = LiteLLMGatewayClient(
        base_url="http://localhost:4000/v1",
        api_key="sk-mcp-corporate-test-key",
        timeout_seconds=0.001,
        mock_llm=False,
    )
    with pytest.raises(TimeoutError):
        client.complete(
            messages=[{"role": "user", "content": "Trigger timeout test"}]
        )