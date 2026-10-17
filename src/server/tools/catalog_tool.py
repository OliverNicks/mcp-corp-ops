"""
Catalog Business Tool for Best4Baby OpenCart Schema.
Retrieves inventory stock levels across product variations (sizes/colors)
by joining oc_product, oc_product_description, and oc_product_option_value.
"""

from collections import defaultdict
import logging
from typing import Any, Dict, List, Optional
from fastmcp import FastMCP

from src.core.db import db
from src.security.schemas import (
    CatalogStockResult,
    ProductOptionStock,
    ProductStockResponse,
)

logger = logging.getLogger("catalog_tool")


def get_product_stock_levels(
    product_id: Optional[int] = None,
    sku: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Retrieves stock levels for an item by product ID or SKU across all option variations.

    Args:
        product_id: Unique OpenCart product identifier (e.g., 1, 2)
        sku: Product model / SKU string (e.g., 'HUPPA-W-3192', 'HUPPA-W-3631')

    Returns:
        Structured dictionary matching CatalogStockResult containing base product info,
        total variation inventory, and individual stock counts per size/color.
    """
    logger.info("Executing get_product_stock_levels(product_id=%s, sku=%s)", product_id, sku)

    if product_id is None and not sku:
        return CatalogStockResult(
            found=False,
            message="Invalid parameters: either 'product_id' or 'sku' must be provided.",
            products=[],
        ).model_dump()

    # Query joining oc_product, oc_product_description, and oc_product_option_value
    sql = """
    SELECT 
        p.product_id,
        p.model,
        p.quantity AS base_quantity,
        p.price,
        p.status,
        pd.name,
        pov.product_option_value_id,
        pov.option_id,
        pov.option_value_id,
        pov.quantity AS option_quantity,
        pov.price AS option_price
    FROM oc_product p
    LEFT JOIN oc_product_description pd 
        ON p.product_id = pd.product_id AND pd.language_id = 1
    LEFT JOIN oc_product_option_value pov 
        ON p.product_id = pov.product_id
    WHERE (:pid_exact IS NOT NULL AND p.product_id = :pid_exact)
       OR (:sku_exact IS NOT NULL AND (LOWER(p.model) = LOWER(:sku_exact) OR p.model LIKE :sku_wildcard))
    ORDER BY p.product_id, pov.option_id, pov.option_value_id
    """

    params: Dict[str, Any] = {
        "pid_exact": product_id,
        "sku_exact": sku.strip() if sku else None,
        "sku_wildcard": f"%{sku.strip()}%" if sku else None,
    }

    try:
        raw_rows = db.execute_query(sql, params)
    except Exception as exc:
        logger.error("Database query error in get_product_stock_levels: %s", exc)
        return CatalogStockResult(
            found=False,
            message=f"Database execution failed: {exc}",
            products=[],
        ).model_dump()

    if not raw_rows:
        return CatalogStockResult(
            found=False,
            message=f"No products found matching product_id={product_id} or sku='{sku}'",
            products=[],
        ).model_dump()

    # Group rows by product_id to aggregate option variations
    grouped: Dict[int, Dict[str, Any]] = defaultdict(lambda: {"info": {}, "variations": []})

    for row in raw_rows:
        pid = row["product_id"]
        if not grouped[pid]["info"]:
            grouped[pid]["info"] = {
                "product_id": pid,
                "model": row["model"],
                "name": row["name"],
                "base_quantity": row["base_quantity"],
                "price": float(row["price"]),
                "status": row["status"],
            }

        # Check if row contains a valid option variation
        if row.get("option_id") is not None and row.get("option_value_id") is not None:
            grouped[pid]["variations"].append(
                ProductOptionStock(
                    option_id=row["option_id"],
                    option_value_id=row["option_value_id"],
                    quantity=row["option_quantity"],
                    price_delta=float(row.get("option_price") or 0.0),
                )
            )

    product_responses: List[ProductStockResponse] = []
    for pid, data in grouped.items():
        info = data["info"]
        vars_list: List[ProductOptionStock] = data["variations"]
        total_var_stock = sum(v.quantity for v in vars_list) if vars_list else info["base_quantity"]

        product_responses.append(
            ProductStockResponse(
                product_id=info["product_id"],
                model=info["model"],
                name=info["name"],
                base_quantity=info["base_quantity"],
                total_variation_stock=total_var_stock,
                price=info["price"],
                status=info["status"],
                variations=vars_list,
            )
        )

    result = CatalogStockResult(
        found=True,
        message=f"Retrieved {len(product_responses)} matching product(s)",
        products=product_responses,
    )

    return result.model_dump()


def register_catalog_tools(mcp: FastMCP) -> None:
    """Registers catalog tools to a FastMCP server instance."""
    mcp.tool(
        name="get_product_stock_levels",
        description="Check product availability and stock counts across variations (sizes/colors) by product ID or SKU.",
    )(get_product_stock_levels)
