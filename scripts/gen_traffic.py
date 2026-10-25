import asyncio
from fastmcp import Client

CALLS = [
    ("get_product_stock_levels", {"product_id": 1}),
    ("get_sales_analytics", {"date_from": "2026-10-01", "date_to": "2026-10-31"}),
    ("execute_safe_query", {"query": "SELECT model, price FROM oc_product", "query_purpose": "demo"}),
    ("execute_safe_query", {"query": "DROP TABLE oc_product;", "query_purpose": "attack"}),
    ("execute_safe_query", {"query": "SELECT email FROM oc_customer", "query_purpose": "gdpr"}),
]

async def main():
    async with Client("http://localhost:8000/sse") as c:
        for _ in range(20):
            for name, args in CALLS:
                await c.call_tool(name, args)
            await asyncio.sleep(0.5)

asyncio.run(main())