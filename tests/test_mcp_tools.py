"""
Unit & Integration Tests for FastMCP Business Tools (catalog_tool & sales_tool).
Verifies stock counts and financial analytics against seeded SQLite fixtures.
Supports both pytest runner and direct execution (`python tests/test_mcp_tools.py`).
"""

try:
    import pytest
except ImportError:
    pytest = None

from data.fixtures.seed_sqlite import seed_sqlite
from src.server.tools.catalog_tool import get_product_stock_levels
from src.server.tools.sales_tool import get_sales_analytics

if pytest:
    @pytest.fixture(scope="session", autouse=True)
    def init_test_db():
        """Ensures test SQLite fixtures are populated before executing tool tests."""
        seed_sqlite()
else:
    def init_test_db():
        seed_sqlite()


# =============================================================================
# 1. Catalog Tool Tests (get_product_stock_levels)
# =============================================================================
def test_catalog_stock_by_product_id():
    """Verify inventory retrieval by specific product ID."""
    result = get_product_stock_levels(product_id=1)

    assert result["found"] is True
    assert len(result["products"]) == 1

    product = result["products"][0]
    assert product["product_id"] == 1
    assert product["model"] == "HUPPA-W-3192"
    assert "Huppa Avery" in product["name"]
    assert product["price"] == 4850.0

    # Verify variations (Sizes 80, 86, 92 with quantities 15, 18, 12)
    assert len(product["variations"]) == 3
    assert product["total_variation_stock"] == 45

    sizes = {v["option_value_id"]: v["quantity"] for v in product["variations"]}
    assert sizes == {80: 15, 86: 18, 92: 12}


def test_catalog_stock_by_sku():
    """Verify inventory retrieval by model / SKU string."""
    result = get_product_stock_levels(sku="HUPPA-W-3631")

    assert result["found"] is True
    assert len(result["products"]) == 1

    product = result["products"][0]
    assert product["product_id"] == 2
    assert product["model"] == "HUPPA-W-3631"
    assert len(product["variations"]) == 3
    assert product["total_variation_stock"] == 32  # 10 + 12 + 10 = 32 in db


def test_catalog_stock_product_without_options():
    """Verify product without option variations returns base quantity."""
    # Product 5 (HUPPA-D-3190) has no options in seed fixtures
    result = get_product_stock_levels(product_id=5)

    assert result["found"] is True
    product = result["products"][0]
    assert product["model"] == "HUPPA-D-3190"
    assert product["variations"] == []
    assert product["total_variation_stock"] == 20
    assert product["base_quantity"] == 20


def test_catalog_stock_not_found():
    """Verify query for non-existent product returns found=False."""
    result = get_product_stock_levels(product_id=99999)

    assert result["found"] is False
    assert result["products"] == []
    assert "No products found" in result["message"]


def test_catalog_stock_missing_parameters():
    """Verify calling without product_id or sku returns validation error."""
    result = get_product_stock_levels()

    assert result["found"] is False
    assert "either 'product_id' or 'sku' must be provided" in result["message"]


# =============================================================================
# 2. Sales Analytics Tool Tests (get_sales_analytics)
# =============================================================================
def test_sales_analytics_completed_orders():
    """Verify sales aggregation for completed orders (status 5) in Oct 2026."""
    result = get_sales_analytics("2026-10-01", "2026-10-31", status_id=5)

    assert result["date_from"] == "2026-10-01"
    assert result["date_to"] == "2026-10-31"
    assert result["status_id"] == 5
    assert result["total_orders"] == 8
    assert result["gross_revenue"] == 37040.0
    assert result["average_order_value"] == 4630.0


def test_sales_analytics_all_order_statuses():
    """Verify sales aggregation across all order statuses (status_id=None)."""
    result = get_sales_analytics("2026-10-01", "2026-10-31")

    assert result["status_id"] is None
    assert result["total_orders"] == 10
    assert result["gross_revenue"] == 43920.0
    assert result["average_order_value"] == 4392.0


def test_sales_analytics_empty_date_range():
    """Verify date range with no orders returns 0 orders and 0.0 revenue."""
    result = get_sales_analytics("2025-01-01", "2025-01-31")

    assert result["total_orders"] == 0
    assert result["gross_revenue"] == 0.0
    assert result["average_order_value"] == 0.0


def test_sales_analytics_invalid_date_format():
    """Verify malformed date strings raise ValueError."""
    if pytest:
        with pytest.raises(ValueError, match="Date formatting error"):
            get_sales_analytics("2026/10/01", "2026-10-31")
    else:
        try:
            get_sales_analytics("2026/10/01", "2026-10-31")
            raise AssertionError("Expected ValueError on invalid date")
        except ValueError as exc:
            assert "Date formatting error" in str(exc)


def test_sales_analytics_inverted_date_range():
    """Verify date_from greater than date_to raises ValueError."""
    if pytest:
        with pytest.raises(ValueError, match="must be before or equal to"):
            get_sales_analytics("2026-11-01", "2026-10-01")
    else:
        try:
            get_sales_analytics("2026-11-01", "2026-10-01")
            raise AssertionError("Expected ValueError on inverted dates")
        except ValueError as exc:
            assert "must be before or equal to" in str(exc)


if __name__ == "__main__":
    init_test_db()
    test_functions = [
        test_catalog_stock_by_product_id,
        test_catalog_stock_by_sku,
        test_catalog_stock_product_without_options,
        test_catalog_stock_not_found,
        test_catalog_stock_missing_parameters,
        test_sales_analytics_completed_orders,
        test_sales_analytics_all_order_statuses,
        test_sales_analytics_empty_date_range,
        test_sales_analytics_invalid_date_format,
        test_sales_analytics_inverted_date_range,
    ]
    print(f"Running {len(test_functions)} tool integration tests...")
    for fn in test_functions:
        fn()
        print(f"  [PASS] {fn.__name__}")
    print("\nAll integration tests passed successfully!")
