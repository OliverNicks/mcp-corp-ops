import os

import httpx
import pytest

from src.gateway.litellm_client import LiteLLMGatewayClient

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_LIVE_FAILOVER") != "1",
    reason="needs: docker compose --profile mock up (set RUN_LIVE_FAILOVER=1)",
)

PRIMARY_ADMIN = "http://localhost:9001/admin/mode"
MSG = [{"role": "user", "content": "How many orders were placed today?"}]


def set_primary(mode: str) -> None:
    httpx.post(PRIMARY_ADMIN, json={"mode": mode}, timeout=5).raise_for_status()


@pytest.fixture(autouse=True)
def restore_primary():
    set_primary("ok")
    yield
    set_primary("ok")


def make_client() -> LiteLLMGatewayClient:
    return LiteLLMGatewayClient(
        base_url="http://localhost:4001/v1",
        api_key="sk-mcp-corporate-test-key",
        timeout=5.0,
        mock_llm=False,
    )


async def test_primary_serves_when_healthy():
    async with make_client() as client:
        result = await client.acomplete(messages=MSG)
    assert "primary" in result.content


@pytest.mark.parametrize("mode", ["500", "429"])
async def test_failover_on_provider_error(mode):
    set_primary(mode)
    async with make_client() as client:
        result = await client.acomplete(messages=MSG)
    assert "fallback" in result.content
    assert result.latency_ms < 5000


async def test_failover_on_primary_timeout():
    set_primary("timeout")  # primary sleeps 6s, router gives up at 2.5s
    async with make_client() as client:
        result = await client.acomplete(messages=MSG)
    assert "fallback" in result.content
    assert result.latency_ms < 5000  # 2.5s timeout + fallback must fit the client SLA