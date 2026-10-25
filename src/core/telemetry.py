"""Prometheus metrics for the MCP platform (Ops-6)."""
import functools
import logging
import threading
import time

from prometheus_client import Counter, Gauge, Histogram, start_http_server

from src.security.ast_guardrails import (
    DDLNotAllowedError,
    DMLNotAllowedError,
    GDPRViolationError,
    InvalidQueryError,
    MultiStatementError,
)

logger = logging.getLogger("telemetry")

# Sub-10ms buckets for cache hits, up to 5s for LLM/DB misses
LATENCY_BUCKETS = (0.001, 0.002, 0.005, 0.01, 0.015, 0.025, 0.05,
                   0.1, 0.25, 0.5, 1.0, 1.5, 2.5, 5.0)

CACHE_HITS = Counter("mcp_cache_hits_total", "Semantic cache hits")
CACHE_MISSES = Counter("mcp_cache_misses_total", "Semantic cache misses")
CACHE_HIT_RATIO = Gauge("mcp_cache_hit_ratio", "Cache hits / (hits + misses)")

REQUEST_DURATION = Histogram(
    "mcp_request_duration_seconds", "Tool call latency",
    ["tool"], buckets=LATENCY_BUCKETS,
)
TOOL_CALLS = Counter("mcp_tool_calls_total", "Tool calls", ["tool", "status"])
GUARDRAIL_REJECTIONS = Counter(
    "mcp_sql_guardrail_rejections_total", "Queries blocked by AST guardrails", ["reason"],
)

_lock = threading.Lock()
_hits = 0
_misses = 0


def _ratio() -> float:
    total = _hits + _misses
    return _hits / total if total else 0.0


CACHE_HIT_RATIO.set_function(_ratio)


def record_cache_hit() -> None:
    global _hits
    with _lock:
        _hits += 1
    CACHE_HITS.inc()


def record_cache_miss() -> None:
    global _misses
    with _lock:
        _misses += 1
    CACHE_MISSES.inc()


def rejection_reason(exc: Exception) -> str:
    if isinstance(exc, DMLNotAllowedError):
        return "dml_blocked"
    if isinstance(exc, DDLNotAllowedError):
        return "ddl_blocked"
    if isinstance(exc, MultiStatementError):
        return "stacked_blocked"
    if isinstance(exc, InvalidQueryError):
        return "invalid_query"
    if isinstance(exc, GDPRViolationError):
        return "gdpr_column_blocked" if "column" in str(exc) else "gdpr_table_blocked"
    return "other"


def record_rejection(exc: Exception) -> None:
    GUARDRAIL_REJECTIONS.labels(reason=rejection_reason(exc)).inc()


def instrumented(tool: str):
    """Decorator: records latency and success/rejected/error status per tool call."""
    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            start = time.perf_counter()
            status = "success"
            try:
                result = fn(*args, **kwargs)
                if isinstance(result, dict) and result.get("status") == "rejected":
                    status = "rejected"
                return result
            except Exception:
                status = "error"
                raise
            finally:
                REQUEST_DURATION.labels(tool=tool).observe(time.perf_counter() - start)
                TOOL_CALLS.labels(tool=tool, status=status).inc()
        return wrapper
    return decorator


_server_started = False


def start_metrics_server(port: int) -> None:
    global _server_started
    if not _server_started:
        start_http_server(port)
        _server_started = True
        logger.info("Prometheus metrics on :%d/metrics", port)
