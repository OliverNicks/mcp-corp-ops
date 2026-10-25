"""
Safe SQL Execution Business Tool with AST Security Sandbox Guardrails.
Orchestrates sqlglot AST parsing, DDL/DML rejection, GDPR filtering,
LIMIT enforcement, and secure query execution against the database.
"""

import logging
import time
from typing import Any

from fastmcp import FastMCP

from src.core.db import db
from src.core.telemetry import instrumented, record_rejection
from src.security.ast_guardrails import (
    SecurityViolationError,
    validate_and_sanitize_query,
)
from src.security.schemas import SafeQueryResult

logger = logging.getLogger("sql_tool")

@instrumented("execute_safe_query")
def execute_safe_query(query: str, query_purpose: str) -> dict[str, Any]:
    """
    Validates and securely executes an ad-hoc SQL query through the AST security guardrails.

    Zero-trust guarantees:
    - Rejects all DDL (DROP, CREATE, ALTER, TRUNCATE) and DML (INSERT, UPDATE, DELETE).
    - Blocks stacked multi-statements separated by semicolons.
    - Prevents GDPR leaks by blacklisting customer/user tables and PII columns.
    - Caps or automatically appends LIMIT 100 to prevent runaway table scans.

    Args:
        query: Raw SQL query string to validate and execute.
        query_purpose: Business description of why this query is needed.

    Returns:
        Structured dictionary matching SafeQueryResult:
        - status: 'success' or 'rejected'
        - sanitized_sql: Mutated safe query that was actually executed
        - row_count: Number of records returned
        - rows: Result rows as a list of dictionaries
        - latency_ms: Execution duration in milliseconds
        - error: Detailed security rejection reason if blocked
    """
    start_time = time.perf_counter()
    logger.info("Executing execute_safe_query with purpose='%s': %s", query_purpose, query)

    # 1. AST Validation & Mutation Pipeline
    try:
        sanitized_sql = validate_and_sanitize_query(query)
    except SecurityViolationError as exc:
        record_rejection(exc)
        elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
        logger.warning("Query rejected by AST guardrails: %s", exc)
        return SafeQueryResult(
            status="rejected",
            sanitized_sql=None,
            row_count=0,
            rows=[],
            latency_ms=elapsed_ms,
            error=str(exc),
        ).model_dump()
    except Exception as exc:
        record_rejection(exc)
        elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
        logger.error("Unexpected error parsing query: %s", exc)
        return SafeQueryResult(
            status="rejected",
            sanitized_sql=None,
            row_count=0,
            rows=[],
            latency_ms=elapsed_ms,
            error=f"Query parsing error: {exc}",
        ).model_dump()

    # 2. Database Execution
    try:
        rows = db.execute_query(sanitized_sql)
        elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
        return SafeQueryResult(
            status="success",
            sanitized_sql=sanitized_sql,
            row_count=len(rows),
            rows=rows,
            latency_ms=elapsed_ms,
            error=None,
        ).model_dump()
    except Exception as exc:
        elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
        logger.error("Database execution error: %s", exc)
        return SafeQueryResult(
            status="rejected",
            sanitized_sql=sanitized_sql,
            row_count=0,
            rows=[],
            latency_ms=elapsed_ms,
            error=f"Database execution error: {exc}",
        ).model_dump()


def register_sql_tools(mcp: FastMCP) -> None:
    """Registers safe SQL query tools to a FastMCP server instance."""
    mcp.tool(
        name="execute_safe_query",
        description="Execute a safe read-only SQL query against store catalog and analytics data. Automatically protected by AST security guardrails against mutations and GDPR leaks.",
    )(execute_safe_query)
