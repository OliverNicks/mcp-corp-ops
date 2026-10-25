"""
Sales Analytics Business Tool for Best4Baby OpenCart Schema.
Aggregates gross revenue, total order volume, and average order value (AOV)
from the oc_order table across configurable date ranges and order statuses.
"""

from datetime import datetime
import logging
from typing import Any, Dict, Optional
from fastmcp import FastMCP

from src.core.db import db
from src.core.telemetry import instrumented
from src.security.schemas import SalesAnalyticsResult

logger = logging.getLogger("sales_tool")


def _normalize_date_range(date_from: str, date_to: str) -> tuple[str, str]:
    """
    Validates and normalizes date range strings to encompass full days.
    Accepts 'YYYY-MM-DD' or 'YYYY-MM-DD HH:MM:SS'.
    """
    date_from = date_from.strip()
    date_to = date_to.strip()

    # Normalize start date
    if len(date_from) == 10:
        datetime.strptime(date_from, "%Y-%m-%d")
        start_ts = f"{date_from} 00:00:00"
    else:
        datetime.strptime(date_from, "%Y-%m-%d %H:%M:%S")
        start_ts = date_from

    # Normalize end date (set to 23:59:59 if only date provided)
    if len(date_to) == 10:
        datetime.strptime(date_to, "%Y-%m-%d")
        end_ts = f"{date_to} 23:59:59"
    else:
        datetime.strptime(date_to, "%Y-%m-%d %H:%M:%S")
        end_ts = date_to

    if start_ts > end_ts:
        raise ValueError(f"Invalid date range: date_from ('{date_from}') must be before or equal to date_to ('{date_to}').")

    return start_ts, end_ts

@instrumented("get_sales_analytics")
def get_sales_analytics(
    date_from: str,
    date_to: str,
    status_id: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Aggregates financial sales metrics from oc_order for business analytics.

    Args:
        date_from: Start date in 'YYYY-MM-DD' or 'YYYY-MM-DD HH:MM:SS' format.
        date_to: End date in 'YYYY-MM-DD' or 'YYYY-MM-DD HH:MM:SS' format.
        status_id: Optional OpenCart order status ID (e.g. 5=Complete, 2=Processing, 1=Pending).
                   If omitted, calculates metrics across all order statuses.

    Returns:
        Structured dictionary matching SalesAnalyticsResult containing:
        - date_from, date_to, status_id
        - total_orders: total count of matching orders
        - gross_revenue: sum of order total amounts (rounded to 2 decimal places)
        - average_order_value: average order amount (gross_revenue / total_orders)
    """
    logger.info(
        "Executing get_sales_analytics(date_from=%s, date_to=%s, status_id=%s)",
        date_from,
        date_to,
        status_id,
    )

    try:
        start_ts, end_ts = _normalize_date_range(date_from, date_to)
    except Exception as exc:
        logger.error("Date validation error in get_sales_analytics: %s", exc)
        raise ValueError(f"Date formatting error: {exc}") from exc

    sql = """
    SELECT 
        COUNT(order_id) AS total_orders,
        COALESCE(SUM(total), 0.0) AS gross_revenue
    FROM oc_order
    WHERE date_added >= :start_date
      AND date_added <= :end_date
      AND (:status_id IS NULL OR order_status_id = :status_id)
    """

    params: Dict[str, Any] = {
        "start_date": start_ts,
        "end_date": end_ts,
        "status_id": status_id,
    }

    try:
        rows = db.execute_query(sql, params)
    except Exception as exc:
        logger.error("Database query failed in get_sales_analytics: %s", exc)
        raise RuntimeError(f"Database query execution error: {exc}") from exc

    row = rows[0] if rows else {"total_orders": 0, "gross_revenue": 0.0}
    total_orders = int(row.get("total_orders", 0))
    gross_revenue = round(float(row.get("gross_revenue", 0.0)), 2)

    aov = round(gross_revenue / total_orders, 2) if total_orders > 0 else 0.0

    result = SalesAnalyticsResult(
        date_from=date_from,
        date_to=date_to,
        status_id=status_id,
        total_orders=total_orders,
        gross_revenue=gross_revenue,
        average_order_value=aov,
    )

    return result.model_dump()


def register_sales_tools(mcp: FastMCP) -> None:
    """Registers sales analytics tools to a FastMCP server instance."""
    mcp.tool(
        name="get_sales_analytics",
        description="Aggregate gross revenue, total order volume, and average order value (AOV) across date ranges and order statuses.",
    )(get_sales_analytics)
