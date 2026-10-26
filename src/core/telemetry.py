"""Prometheus metrics for the MCP platform (Ops-6)."""

import functools
import logging
import threading
import time

from prometheus_client import Counter, Gauge, Histogram, start_http_server

import atexit
from typing import Any

from src.core.config import settings

from src.security.ast_guardrails import (
    DDLNotAllowedError,
    DMLNotAllowedError,
    GDPRViolationError,
    InvalidQueryError,
    MultiStatementError,
)

logger = logging.getLogger("telemetry")

# Sub-10ms buckets for cache hits, up to 5s for LLM/DB misses
LATENCY_BUCKETS = (
    0.001,
    0.002,
    0.005,
    0.01,
    0.015,
    0.025,
    0.05,
    0.1,
    0.25,
    0.5,
    1.0,
    1.5,
    2.5,
    5.0,
)

CACHE_HITS = Counter("mcp_cache_hits_total", "Semantic cache hits")
CACHE_MISSES = Counter("mcp_cache_misses_total", "Semantic cache misses")
CACHE_HIT_RATIO = Gauge("mcp_cache_hit_ratio", "Cache hits / (hits + misses)")

REQUEST_DURATION = Histogram(
    "mcp_request_duration_seconds",
    "Tool call latency",
    ["tool"],
    buckets=LATENCY_BUCKETS,
)
TOOL_CALLS = Counter("mcp_tool_calls_total", "Tool calls", ["tool", "status"])
GUARDRAIL_REJECTIONS = Counter(
    "mcp_sql_guardrail_rejections_total",
    "Queries blocked by AST guardrails",
    ["reason"],
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

_langfuse = None
_langfuse_failed = False


def get_langfuse():
    """Lazy Langfuse client. Returns None when disabled or unavailable."""
    global _langfuse, _langfuse_failed
    if not settings.langfuse_enabled or _langfuse_failed:
        return None
    if _langfuse is None:
        try:
            from langfuse import Langfuse

            _langfuse = Langfuse(
                public_key=settings.langfuse_public_key,
                secret_key=settings.langfuse_secret_key,
                host=settings.langfuse_host,
            )
            atexit.register(_langfuse.flush)
        except Exception as exc:
            _langfuse_failed = True
            logger.warning("Langfuse disabled: %s", exc)
            return None
    return _langfuse


def _clip(value: Any, limit: int = 1000) -> Any:
    if isinstance(value, str) and len(value) > limit:
        return value[:limit] + "...[truncated]"
    return value


def _summarize(result: Any) -> Any:
    """Trace-friendly output: keep scalars, replace big lists with their length."""
    if isinstance(result, dict):
        return {
            k: (f"<list of {len(v)}>" if isinstance(v, list) else _clip(v))
            for k, v in result.items()
        }
    return _clip(str(result))

def instrumented(tool: str):
    """Decorator: Prometheus latency/status plus a Langfuse trace per tool call."""
    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            start = time.perf_counter()
            status = "success"
            result = None
            error = None

            lf = get_langfuse()
            trace = span = None
            if lf:
                try:
                    tool_input = {k: _clip(v) for k, v in kwargs.items()}
                    trace = lf.trace(name=tool, input=tool_input, tags=["mcp-tool"])
                    span = trace.span(name=tool, input=tool_input)
                except Exception as exc:
                    logger.debug("Langfuse trace start failed: %s", exc)

            try:
                result = fn(*args, **kwargs)
                if isinstance(result, dict) and result.get("status") == "rejected":
                    status = "rejected"
                return result
            except Exception as exc:
                status = "error"
                error = str(exc)
                raise
            finally:
                elapsed = time.perf_counter() - start
                REQUEST_DURATION.labels(tool=tool).observe(elapsed)
                TOOL_CALLS.labels(tool=tool, status=status).inc()
                if span is not None:
                    try:
                        output = _summarize(result) if result is not None else {"error": error}
                        level = {"success": "DEFAULT", "rejected": "WARNING", "error": "ERROR"}[status]
                        span.end(output=output, level=level, status_message=status)
                        trace.update(output=output)
                    except Exception as exc:
                        logger.debug("Langfuse trace end failed: %s", exc)
        return wrapper
    return decorator

_server_started = False


def start_metrics_server(port: int) -> None:
    global _server_started
    if not _server_started:
        start_http_server(port)
        _server_started = True
        logger.info("Prometheus metrics on :%d/metrics", port)
