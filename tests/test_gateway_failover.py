import httpx
import pytest

from src.gateway.litellm_client import LiteLLMGatewayClient

MSG = [{"role": "user", "content": "How many orders were placed today?"}]


def _client_with(handler) -> LiteLLMGatewayClient:
    client = LiteLLMGatewayClient(mock_llm=False)
    client._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return client


async def test_mock_profile_completion():
    client = LiteLLMGatewayClient(mock_llm=True)
    result = await client.acomplete(messages=MSG)
    assert result.simulated is True
    assert result.latency_ms < 2500


async def test_gateway_timeout_enforcement():
    def handler(request):
        raise httpx.ReadTimeout("too slow", request=request)

    with pytest.raises(TimeoutError):
        await _client_with(handler).acomplete(messages=MSG)


@pytest.mark.parametrize("status", [429, 500, 503])
async def test_gateway_http_errors_propagate(status):
    client = _client_with(lambda r: httpx.Response(status))
    with pytest.raises(RuntimeError, match=str(status)):
        await client.acomplete(messages=MSG)


async def test_gateway_parses_real_response_shape():
    body = {
        "model": "gpt-4o-mini",
        "choices": [{"message": {"content": "SELECT 1"}}],
        "usage": {"prompt_tokens": 3, "completion_tokens": 2, "total_tokens": 5},
    }
    result = await _client_with(lambda r: httpx.Response(200, json=body)).acomplete(messages=MSG)
    assert result.content == "SELECT 1"
    assert result.usage.total_tokens == 5
    assert result.simulated is False