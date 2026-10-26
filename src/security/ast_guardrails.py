"""
Zero-Trust Abstract Syntax Tree (AST) Security Sandbox Guardrails.
Enforces read-only safety, GDPR compliance, and unconstrained scan limits using sqlglot.
"""

import logging

import sqlglot
from sqlglot import exp
from sqlglot.errors import ParseError

from src.core.config import settings

logger = logging.getLogger("ast_guardrails")


# =============================================================================
# 1. Custom Security Exceptions
# =============================================================================
class SecurityViolationError(Exception):
    """Base exception for all SQL security guardrail violations."""


class DDLNotAllowedError(SecurityViolationError):
    """Raised when Data Definition Language (CREATE, DROP, ALTER, etc.) is detected."""


class DMLNotAllowedError(SecurityViolationError):
    """Raised when Data Manipulation Language (INSERT, UPDATE, DELETE, etc.) is detected."""


class GDPRViolationError(SecurityViolationError):
    """Raised when queries attempt to read restricted PII tables or sensitive columns."""


class MultiStatementError(SecurityViolationError):
    """Raised when stacked/multiple queries separated by semicolons are submitted."""


class InvalidQueryError(SecurityViolationError):
    """Raised when the query cannot be parsed as valid SQL or is empty."""


# =============================================================================
# 2. Security Blacklists & Constrained Types
# =============================================================================
RESTRICTED_TABLES: set[str] = {
    "oc_customer",
    "oc_user",
    "customer",
    "user",
    "admin",
    "oc_customer_group",
    "oc_customer_login",
    "oc_customer_ip",
    "oc_user_group",
    "users",
    "customers",
    "administrators",
    "admin_users",
}

RESTRICTED_COLUMNS: set[str] = {
    "telephone",
    "email",
    "password",
    "salt",
    "token",
    "ip",
    "card_num",
    "credit_card",
    "cvv",
    "card_number",
    "ssn",
    "secret",
}

FORBIDDEN_DML_TYPES = (
    exp.Insert,
    exp.Update,
    exp.Delete,
    exp.Into,
)

FORBIDDEN_DDL_TYPES = (
    exp.Drop,
    exp.Alter,
    exp.Create,
    exp.TruncateTable,
    exp.Command,
    exp.Transaction,
    exp.Commit,
    exp.Rollback,
    exp.Set,
    exp.Kill,
    exp.Pragma,
    exp.Grant,
    exp.Revoke,
)


# =============================================================================
# 3. Validation & Sanitization Engine
# =============================================================================
def validate_and_sanitize_query(
    raw_query: str,
    dialect: str | None = None,
    max_limit: int = 100,
) -> str:
    """
    Validates a SQL query using AST inspection and mutates it with safe execution bounds.

    Args:
        raw_query: Raw SQL string submitted by the LLM or agent.
        dialect: Dialect to parse and emit (defaults to active db_engine: 'mysql' or 'sqlite').
        max_limit: Maximum allowed row limit to enforce (default: 100).

    Returns:
        Sanitized, safe SQL query ready for execution.

    Raises:
        InvalidQueryError: If the SQL string is empty or syntactically invalid.
        MultiStatementError: If multiple statements separated by semicolons are present.
        DDLNotAllowedError: If DDL operations (DROP, ALTER, CREATE, TRUNCATE) are detected.
        DMLNotAllowedError: If DML mutation operations (INSERT, UPDATE, DELETE) are detected.
        GDPRViolationError: If restricted tables or sensitive PII columns are referenced.
    """
    if not raw_query or not raw_query.strip():
        raise InvalidQueryError("Query cannot be empty or whitespace.")

    target_dialect = dialect or ("mysql" if settings.db_engine == "mysql" else "sqlite")

    # 1. Multi-Statement Inspection (Prevent Stacked Queries Injection)
    try:
        parsed_statements = [
            stmt for stmt in sqlglot.parse(raw_query, read="mysql") if stmt is not None
        ]
    except ParseError as exc:
        logger.warning("SQL ParseError encountered: %s", exc)
        raise InvalidQueryError(f"Malformed SQL query syntax: {exc}") from exc

    if not parsed_statements:
        raise InvalidQueryError("No valid SQL statement found.")

    if len(parsed_statements) > 1:
        raise MultiStatementError(
            f"Multi-statement execution rejected: detected {len(parsed_statements)} statements. "
            "Stacked queries separated by semicolons are prohibited."
        )

    ast = parsed_statements[0]

    # 2. Strict Read-Only Root & Operation Inspection
    if not isinstance(ast, (exp.Select, exp.Union)):
        # Inspect root node to classify DDL vs DML
        if isinstance(ast, FORBIDDEN_DML_TYPES):
            raise DMLNotAllowedError(f"DML operation '{type(ast).__name__}' is strictly forbidden.")
        if isinstance(ast, FORBIDDEN_DDL_TYPES):
            raise DDLNotAllowedError(f"DDL operation '{type(ast).__name__}' is strictly forbidden.")
        raise SecurityViolationError(
            f"Query root must be a SELECT or UNION statement, got '{type(ast).__name__}'."
        )

    # Deep AST tree inspection for embedded/subquery mutation nodes
    for node in ast.walk():
        if isinstance(node, FORBIDDEN_DML_TYPES):
            raise DMLNotAllowedError(
                f"Embedded DML operation '{type(node).__name__}' is forbidden."
            )
        if isinstance(node, FORBIDDEN_DDL_TYPES):
            raise DDLNotAllowedError(
                f"Embedded DDL operation '{type(node).__name__}' is forbidden."
            )

    # 3. GDPR & Privacy Access Control (Table & Column Walking)
    # Check Table References
    for table_node in ast.find_all(exp.Table):
        table_name = table_node.name.lower()
        if table_name in RESTRICTED_TABLES:
            raise GDPRViolationError(
                f"GDPR Policy Violation: Access to restricted table '{table_name}' is blocked."
            )

    # Check Column References
    for col_node in ast.find_all(exp.Column):
        col_name = col_node.name.lower()
        if col_name in RESTRICTED_COLUMNS:
            raise GDPRViolationError(
                f"GDPR Policy Violation: Access to sensitive column '{col_name}' is blocked."
            )

    # 4. On-the-Fly AST Mutation: Enforce LIMIT 100
    limit_node = ast.find(exp.Limit)
    if limit_node is None:
        # No limit specified: inject LIMIT 100
        ast = ast.limit(max_limit)
    else:
        # Existing limit specified: cap it if it exceeds max_limit
        try:
            current_limit = int(limit_node.expression.this)
            if current_limit > max_limit:
                logger.info("Capping requested limit from %d to %d", current_limit, max_limit)
                limit_node.set("expression", exp.Literal.number(max_limit))
        except (ValueError, AttributeError):
            # Complex limit expression: force numeric safe cap
            limit_node.set("expression", exp.Literal.number(max_limit))

    # 5. Emit Clean Sanitized SQL
    sanitized_sql = ast.sql(dialect=target_dialect)
    return sanitized_sql
