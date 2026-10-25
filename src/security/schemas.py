"""
Strict Pydantic Input/Output Validation Schemas for MCP Tools and AST Guardrails.
Provides strongly-typed schemas for catalog stock, sales analytics, and safe query execution.
"""

from typing import Any

from pydantic import BaseModel, Field


# =============================================================================
# 1. Catalog Tool Schemas
# =============================================================================
class ProductOptionStock(BaseModel):
    """Stock level and price variance for a specific option/size variation."""
    option_id: int = Field(..., description="Option type ID (e.g., 1 for size, 2 for color)")
    option_value_id: int = Field(..., description="Specific variation value ID (e.g., size 80, 86, 92)")
    quantity: int = Field(..., description="Available inventory count for this variation")
    price_delta: float = Field(default=0.0, description="Price adjustment relative to base product price")


class ProductStockResponse(BaseModel):
    """Aggregated inventory status for a catalog product across all variations."""
    product_id: int = Field(..., description="Unique OpenCart product ID")
    model: str = Field(..., description="Product SKU / Model identifier")
    name: str | None = Field(None, description="Localized product name")
    base_quantity: int = Field(..., description="Total unassigned base product stock")
    total_variation_stock: int = Field(..., description="Sum of stock across all option variations")
    price: float = Field(..., description="Base product price in store currency")
    status: int = Field(..., description="Catalog visibility status (1=active, 0=disabled)")
    variations: list[ProductOptionStock] = Field(
        default_factory=list,
        description="List of specific size/color options and their stock levels",
    )


class CatalogStockResult(BaseModel):
    """Root return schema for catalog stock queries."""
    found: bool = Field(..., description="Whether matching products were found in the database")
    message: str | None = Field(None, description="Informational message or error summary")
    products: list[ProductStockResponse] = Field(
        default_factory=list,
        description="List of matching products and their stock breakdowns",
    )


# =============================================================================
# 2. Sales Analytics Tool Schemas
# =============================================================================
class SalesAnalyticsResult(BaseModel):
    """Financial aggregation metrics for business sales analysis."""
    date_from: str = Field(..., description="Start of date range (YYYY-MM-DD)")
    date_to: str = Field(..., description="End of date range (YYYY-MM-DD)")
    status_id: int | None = Field(None, description="Filtered order status ID (e.g., 5=Complete)")
    total_orders: int = Field(..., description="Total number of matching orders")
    gross_revenue: float = Field(..., description="Gross revenue sum for matching orders")
    average_order_value: float = Field(..., description="Average order value (AOV)")


# =============================================================================
# 3. SQL Security Tool Schemas
# =============================================================================
class SafeQueryInput(BaseModel):
    """Input payload for executing dynamic queries through the AST sandbox."""
    query: str = Field(..., min_length=5, description="Raw SQL SELECT statement to sanitize and execute")
    query_purpose: str = Field(..., min_length=3, description="Business justification for executing the query")


class SafeQueryResult(BaseModel):
    """Structured response from the AST-guarded SQL execution tool."""
    status: str = Field(..., description="Execution status: 'success', 'cached', or 'rejected'")
    sanitized_sql: str | None = Field(None, description="Final AST-mutated SQL query that was executed")
    row_count: int = Field(default=0, description="Number of rows returned")
    rows: list[dict[str, Any]] = Field(default_factory=list, description="Result rows as key-value dictionaries")
    latency_ms: float = Field(default=0.0, description="Total execution time in milliseconds")
    error: str | None = Field(None, description="AST rejection reason or execution error if failed")
