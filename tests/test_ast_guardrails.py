"""
AST SQL Security Sandbox Guardrail Test Suite.
Verifies 100% block rate on DDL, DML, GDPR leaks, stacked injections,
and ensures automatic LIMIT 100 injection and capping.
Supports both pytest runner and direct execution (`python tests/test_ast_guardrails.py`).
"""

try:
    import pytest
except ImportError:
    pytest = None

from data.fixtures.seed_sqlite import seed_sqlite
from src.security.ast_guardrails import (
    DDLNotAllowedError,
    DMLNotAllowedError,
    GDPRViolationError,
    InvalidQueryError,
    MultiStatementError,
    validate_and_sanitize_query,
)
from src.server.tools.sql_tool import execute_safe_query

# Initialize SQLite test fixtures
seed_sqlite()


# =============================================================================
# 1. Legitimate Queries & LIMIT Enforcer Tests
# =============================================================================
def test_legit_select_injects_limit_100():
    """Verify clean SELECT gets LIMIT 100 automatically injected."""
    sanitized = validate_and_sanitize_query("SELECT product_id, model FROM oc_product")
    assert "LIMIT 100" in sanitized
    assert "oc_product" in sanitized


def test_legit_select_preserves_smaller_limit():
    """Verify limit smaller than 100 is preserved without modification."""
    sanitized = validate_and_sanitize_query("SELECT product_id FROM oc_product LIMIT 25")
    assert "LIMIT 25" in sanitized


def test_legit_select_caps_oversized_limit():
    """Verify limits exceeding 100 are mutated and capped to 100."""
    sanitized = validate_and_sanitize_query("SELECT product_id FROM oc_product LIMIT 500")
    assert "LIMIT 100" in sanitized
    assert "LIMIT 500" not in sanitized


def test_legit_select_with_joins():
    """Verify multi-table joins on legitimate tables succeed."""
    query = """
    SELECT p.product_id, p.model, pov.quantity
    FROM oc_product p
    JOIN oc_product_option_value pov ON p.product_id = pov.product_id
    WHERE p.status = 1
    """
    sanitized = validate_and_sanitize_query(query)
    assert "JOIN" in sanitized
    assert "LIMIT 100" in sanitized


def test_legit_select_aggregations():
    """Verify analytics aggregations (COUNT, SUM, AVG) are permitted."""
    query = "SELECT COUNT(order_id) AS total_orders, SUM(total) AS gross_revenue FROM oc_order"
    sanitized = validate_and_sanitize_query(query)
    assert "COUNT" in sanitized
    assert "SUM" in sanitized
    assert "LIMIT 100" in sanitized


def test_legit_select_union():
    """Verify UNION statements are parsed and receive LIMIT enforcement."""
    query = "SELECT product_id FROM oc_product UNION SELECT product_id FROM oc_product_option_value"
    sanitized = validate_and_sanitize_query(query)
    assert "UNION" in sanitized
    assert "LIMIT 100" in sanitized


# =============================================================================
# 2. Destructive DDL Rejection Tests (100% Block Rate)
# =============================================================================
DDL_TEST_CASES = [
    "DROP TABLE oc_product;",
    "DROP TABLE oc_order;",
    "DROP DATABASE best4baby;",
    "TRUNCATE TABLE oc_order;",
    "ALTER TABLE oc_product ADD COLUMN evil INT;",
    "ALTER TABLE oc_order DROP COLUMN total;",
    "CREATE TABLE backdoor (id INT);",
    "CREATE VIEW backdoor_view AS SELECT 1;",
]


def test_ddl_operations_blocked():
    """Verify all DDL statements raise DDLNotAllowedError."""
    for query in DDL_TEST_CASES:
        try:
            validate_and_sanitize_query(query)
            raise AssertionError(f"Failed to block DDL query: {query}") 
        except DDLNotAllowedError:
            pass  # Expected


# =============================================================================
# 3. Data Mutation DML Rejection Tests (100% Block Rate)
# =============================================================================
DML_TEST_CASES = [
    "DELETE FROM oc_order WHERE order_id > 0;",
    "DELETE FROM oc_product;",
    "UPDATE oc_product SET price = 0.0;",
    "UPDATE oc_order SET total = 999999.0 WHERE order_id = 1;",
    "INSERT INTO oc_product (model, quantity) VALUES ('MALICIOUS', 999);",
    "INSERT INTO oc_order SELECT * FROM oc_order;",
    "SELECT * INTO hacked_table FROM oc_product;",
]


def test_dml_operations_blocked():
    """Verify all DML mutation statements raise DMLNotAllowedError."""
    for query in DML_TEST_CASES:
        try:
            validate_and_sanitize_query(query)
            raise AssertionError(f"Failed to block DML query: {query}")
        except DMLNotAllowedError:
            pass  # Expected


# =============================================================================
# 4. GDPR & Privacy Rejection Tests (100% Block Rate)
# =============================================================================
GDPR_TABLE_TEST_CASES = [
    "SELECT * FROM oc_customer;",
    "SELECT customer_id, firstname FROM oc_customer;",
    "SELECT * FROM oc_user;",
    "SELECT user_id, username FROM oc_user;",
    "SELECT * FROM customer;",
    "SELECT * FROM user;",
    "SELECT * FROM admin;",
    "SELECT * FROM oc_customer_group;",
    "SELECT * FROM oc_customer_login;",
    "SELECT p.model FROM oc_product p JOIN oc_customer c ON p.product_id = c.customer_id;",
    "SELECT * FROM oc_product WHERE product_id IN (SELECT customer_id FROM oc_customer);",
    "SELECT * FROM oc_product WHERE product_id IN (SELECT user_id FROM oc_user);",
]


def test_gdpr_table_access_blocked():
    """Verify access to restricted customer/user tables raises GDPRViolationError."""
    for query in GDPR_TABLE_TEST_CASES:
        try:
            validate_and_sanitize_query(query)
            raise AssertionError(f"Failed to block GDPR table access: {query}")
        except GDPRViolationError:
            pass  # Expected


GDPR_COLUMN_TEST_CASES = [
    "SELECT telephone FROM oc_product;",
    "SELECT email FROM oc_product;",
    "SELECT password FROM oc_product;",
    "SELECT salt FROM oc_product;",
    "SELECT token FROM oc_product;",
    "SELECT ip FROM oc_product;",
    "SELECT card_num FROM oc_order;",
    "SELECT credit_card FROM oc_order;",
    "SELECT cvv FROM oc_order;",
    "SELECT ssn FROM oc_order;",
]


def test_gdpr_column_access_blocked():
    """Verify access to sensitive PII columns raises GDPRViolationError."""
    for query in GDPR_COLUMN_TEST_CASES:
        try:
            validate_and_sanitize_query(query)
            raise AssertionError(f"Failed to block sensitive PII column: {query}")
        except GDPRViolationError:
            pass  # Expected


# =============================================================================
# 5. Stacked Injections & Syntax Tests (100% Block Rate)
# =============================================================================
STACKED_TEST_CASES = [
    "SELECT * FROM oc_product; DROP TABLE oc_order;",
    "SELECT 1; SELECT 2;",
    "SELECT product_id FROM oc_product; DELETE FROM oc_order;",
    "SELECT * FROM oc_product; TRUNCATE TABLE oc_order;",
]


def test_stacked_statements_blocked():
    """Verify multi-statement stacked injections raise MultiStatementError."""
    for query in STACKED_TEST_CASES:
        try:
            validate_and_sanitize_query(query)
            raise AssertionError(f"Failed to block stacked multi-statement: {query}")
        except MultiStatementError:
            pass  # Expected


def test_empty_and_malformed_queries_blocked():
    """Verify empty or unparseable queries raise InvalidQueryError."""
    invalid_cases = [
        "",
        "   ",
        "SELECT FROM WHERE",
        "NOT A SQL QUERY",
    ]
    for query in invalid_cases:
        try:
            validate_and_sanitize_query(query)
            raise AssertionError(f"Failed to block malformed query: {query}") 
        except InvalidQueryError:
            pass  # Expected


# =============================================================================
# 6. End-to-End Safe Query Tool Tests (execute_safe_query)
# =============================================================================
def test_execute_safe_query_success():
    """Verify execute_safe_query returns valid records for legitimate queries."""
    result = execute_safe_query(
        query="SELECT product_id, model, price FROM oc_product WHERE status = 1",
        query_purpose="Check active catalog items for customer display",
    )
    assert result["status"] == "success"
    assert result["row_count"] > 0
    assert len(result["rows"]) == result["row_count"]
    assert "LIMIT 100" in result["sanitized_sql"]
    assert result["error"] is None


def test_execute_safe_query_rejection():
    """Verify execute_safe_query rejects attacks with structured rejection envelope."""
    result = execute_safe_query(
        query="DROP TABLE oc_product;",
        query_purpose="Destructive penetration test attempt",
    )
    assert result["status"] == "rejected"
    assert result["row_count"] == 0
    assert result["rows"] == []
    assert "strictly forbidden" in result["error"]


def test_execute_safe_query_gdpr_rejection():
    """Verify execute_safe_query rejects customer PII leaks."""
    result = execute_safe_query(
        query="SELECT firstname, email, telephone FROM oc_customer",
        query_purpose="Exfiltrate customer PII",
    )
    assert result["status"] == "rejected"
    assert "GDPR Policy Violation" in result["error"]


if __name__ == "__main__":
    test_functions = [
        test_legit_select_injects_limit_100,
        test_legit_select_preserves_smaller_limit,
        test_legit_select_caps_oversized_limit,
        test_legit_select_with_joins,
        test_legit_select_aggregations,
        test_legit_select_union,
        test_ddl_operations_blocked,
        test_dml_operations_blocked,
        test_gdpr_table_access_blocked,
        test_gdpr_column_access_blocked,
        test_stacked_statements_blocked,
        test_empty_and_malformed_queries_blocked,
        test_execute_safe_query_success,
        test_execute_safe_query_rejection,
        test_execute_safe_query_gdpr_rejection,
    ]

    total_scenarios = (
        6  # legit
        + len(DDL_TEST_CASES)
        + len(DML_TEST_CASES)
        + len(GDPR_TABLE_TEST_CASES)
        + len(GDPR_COLUMN_TEST_CASES)
        + len(STACKED_TEST_CASES)
        + 4  # malformed
        + 3  # tool e2e
    )

    print(f"Executing AST Security Sandbox Guardrail Suite ({total_scenarios} test scenarios across {len(test_functions)} test functions)...")
    for fn in test_functions:
        fn()
        print(f"  [PASS] {fn.__name__}")

    print(f"\n100% BLOCK RATE VERIFIED on all {total_scenarios} attack and validation test cases!")
