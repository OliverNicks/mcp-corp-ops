from prometheus_client import REGISTRY

from data.fixtures.seed_sqlite import seed_sqlite
from src.server.tools.sql_tool import execute_safe_query

seed_sqlite()


def _val(name, labels=None):
    return REGISTRY.get_sample_value(name, labels or {}) or 0.0


def test_rejection_counter_increments():
    labels = {"reason": "ddl_blocked"}
    before = _val("mcp_sql_guardrail_rejections_total", labels)
    execute_safe_query("DROP TABLE oc_product;", "test")
    assert _val("mcp_sql_guardrail_rejections_total", labels) == before + 1


def test_tool_call_counter_and_latency():
    labels = {"tool": "execute_safe_query", "status": "success"}
    before = _val("mcp_tool_calls_total", labels)
    execute_safe_query("SELECT product_id FROM oc_product", "test")
    assert _val("mcp_tool_calls_total", labels) == before + 1
