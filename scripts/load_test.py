"""Async load test: N concurrent MCP sessions over SSE (Ops-9, no Locust/gevent)."""
import argparse
import asyncio
import random
import sys
import time
from collections import defaultdict

from fastmcp import Client

REPEAT_QUERIES = [
    "SELECT model, price FROM oc_product WHERE status = 1",
    "SELECT COUNT(order_id) AS orders, SUM(total) AS revenue FROM oc_order",
]
JOIN_QUERY = (
    "SELECT p.model, pd.name, SUM(pov.quantity) AS stock "
    "FROM oc_product p "
    "JOIN oc_product_description pd ON p.product_id = pd.product_id "
    "JOIN oc_product_option_value pov ON p.product_id = pov.product_id "
    "GROUP BY p.model, pd.name ORDER BY stock DESC"
)
ATTACKS = ["DROP TABLE oc_product;", "SELECT email FROM oc_customer"]

# (weight, label, factory -> (tool, args))
TASKS = [
    (5, "stock (repeated)", lambda: ("get_product_stock_levels",
        {"product_id": random.choice((1, 2, 4, 5, 6, 7))})),
    (3, "sql (repeated)", lambda: ("execute_safe_query",
        {"query": random.choice(REPEAT_QUERIES), "query_purpose": "load test"})),
    (3, "sales (varied dates)", lambda: ("get_sales_analytics",
        {"date_from": "2026-10-01", "date_to": f"2026-10-{random.randint(1, 11):02d}"})),
    (2, "sql (join)", lambda: ("execute_safe_query",
        {"query": JOIN_QUERY, "query_purpose": "load test"})),
    (1, "sql (blocked)", lambda: ("execute_safe_query",
        {"query": random.choice(ATTACKS), "query_purpose": "load test attack"})),
]
WEIGHTS = [t[0] for t in TASKS]


def pct(sorted_ms, p):
    if not sorted_ms:
        return 0.0
    return sorted_ms[min(len(sorted_ms) - 1, int(len(sorted_ms) * p))]


async def worker(idx, url, spawn_rate, deadline, latencies, errors):
    await asyncio.sleep(idx / spawn_rate)  # ramp-up
    try:
        async with Client(url) as client:
            while time.monotonic() < deadline:
                _, label, make = random.choices(TASKS, weights=WEIGHTS)[0]
                tool, args = make()
                t0 = time.perf_counter()
                try:
                    await client.call_tool(tool, args)
                    latencies[label].append((time.perf_counter() - t0) * 1000)
                except Exception as exc:
                    errors[label].append(repr(exc)[:200])
                await asyncio.sleep(random.uniform(0.5, 2))
    except Exception as exc:
        errors["connection"].append(repr(exc)[:200])


async def main(args):
    latencies, errors = defaultdict(list), defaultdict(list)
    url = args.host.rstrip("/") + "/sse"
    start = time.monotonic()
    deadline = start + args.run_time
    await asyncio.gather(*(
        worker(i, url, args.spawn_rate, deadline, latencies, errors)
        for i in range(args.users)
    ))
    elapsed = time.monotonic() - start

    all_ms = sorted(ms for v in latencies.values() for ms in v)
    total_ok = len(all_ms)
    total_err = sum(len(v) for v in errors.values())

    print("\n# Load Test Report\n")
    print(f"users={args.users} spawn_rate={args.spawn_rate}/s run_time={args.run_time}s "
          f"elapsed={elapsed:.1f}s\n")
    print("| Request | OK | Failed | p50 ms | p95 ms | p99 ms | max ms |")
    print("|---|---|---|---|---|---|---|")
    for label in sorted(set(latencies) | set(errors)):
        ms = sorted(latencies[label])
        print(f"| {label} | {len(ms)} | {len(errors[label])} | {pct(ms, .50):.1f} | "
              f"{pct(ms, .95):.1f} | {pct(ms, .99):.1f} | {(ms[-1] if ms else 0):.1f} |")
    print(f"| **TOTAL** | {total_ok} | {total_err} | {pct(all_ms, .50):.1f} | "
          f"{pct(all_ms, .95):.1f} | {pct(all_ms, .99):.1f} | {(all_ms[-1] if all_ms else 0):.1f} |")
    print(f"\nThroughput: {total_ok / elapsed:.1f} req/s")

    if total_err:
        print("\n## Sample errors")
        for label, errs in errors.items():
            for e in errs[:3]:
                print(f"- {label}: {e}")
    return 1 if total_err else 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="http://localhost:8000")
    ap.add_argument("--users", type=int, default=50)
    ap.add_argument("--spawn-rate", type=float, default=5)
    ap.add_argument("--run-time", type=int, default=60)
    sys.exit(asyncio.run(main(ap.parse_args())))