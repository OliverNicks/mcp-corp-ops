"""
Integration & Unit Test Suite for Redis Stack HNSW Semantic Cache.
Verifies:
- RediSearch HNSW Index creation with exact 384-dimensional COSINE schema.
- Sub-15ms cache hit latency SLA.
- Exact query hits (similarity = 1.0).
- Paraphrased query hits (similarity >= 0.94).
- Semantically distinct query misses (similarity < 0.94).
- TTL expiration and cache invalidation.
- Graceful in-memory fallback when Redis is offline.

Supports both pytest runner and direct execution (`python tests/test_semantic_cache.py`).
"""

import time
from typing import List

from src.cache.semantic_cache import (
    DOC_PREFIX,
    INDEX_NAME,
    MockRedisStackClient,
    SemanticCache,
)


def test_index_initialization_and_schema():
    """Verify HNSW vector index is initialized with exact schema and prefix."""
    mock_client = MockRedisStackClient()
    cache = SemanticCache(client=mock_client, index_name="idx:semantic_cache", doc_prefix="mcp:cache:")

    # Verify index created in Redis
    assert "idx:semantic_cache" in mock_client.indices
    created_args = [str(a) for a in mock_client.indices["idx:semantic_cache"]["args"]]

    assert "FT.CREATE" in created_args
    assert "idx:semantic_cache" in created_args
    assert "PREFIX" in created_args
    assert "mcp:cache:" in created_args
    assert "SCHEMA" in created_args
    assert "prompt" in created_args
    assert "response" in created_args
    assert "vector" in created_args
    assert "VECTOR" in created_args
    assert "HNSW" in created_args
    assert "FLOAT32" in created_args
    assert "384" in created_args
    assert "COSINE" in created_args


def test_exact_query_cache_hit():
    """Verify exact query returns immediate cache hit with similarity ~1.0."""
    mock_client = MockRedisStackClient()
    cache = SemanticCache(client=mock_client)

    prompt = "What is the stock level for product 42?"
    response_payload = {
        "product_id": 42,
        "model": "Huppa Avery",
        "total_stock": 85,
        "status": "in_stock",
    }

    key = cache.set(prompt, response_payload)
    assert key.startswith(DOC_PREFIX)

    result = cache.lookup(prompt)
    assert result is not None
    assert result["hit"] is True
    assert abs(result["similarity"] - 1.0) < 1e-3
    assert result["response"] == response_payload
    assert result["latency_ms"] < 15.0


def test_paraphrased_query_cache_hit():
    """Verify semantically equivalent queries hit cache above the 0.94 threshold."""
    mock_client = MockRedisStackClient()
    cache = SemanticCache(client=mock_client)

    original_prompt = "What are the sales figures for last week?"
    response_data = {"gross_revenue": 24500.0, "orders": 182, "aov": 134.62}

    cache.set(original_prompt, response_data)

    paraphrases = [
        "What were the sales figures for last week?",
        "What are the sales numbers for last week?",
    ]

    for para in paraphrases:
        result = cache.lookup(para)
        assert result is not None, f"Expected cache hit for paraphrase: '{para}'"
        assert result["hit"] is True
        assert result["similarity"] >= 0.94, f"Similarity {result['similarity']} < 0.94 for '{para}'"
        assert result["response"] == response_data
        print(f"  [Paraphrase HIT] '{para}' -> similarity={result['similarity']:.4f}")


def test_semantically_distinct_query_miss():
    """Verify unrelated queries miss the cache with similarity strictly < 0.94."""
    mock_client = MockRedisStackClient()
    cache = SemanticCache(client=mock_client)

    cache.set(
        "What are the sales figures for last week?",
        {"gross_revenue": 24500.0, "orders": 182},
    )

    unrelated_queries = [
        "How do I bake a chocolate cake with strawberries?",
        "Where is the nearest gas station?",
        "What is the return policy for defective shoes?",
    ]

    for query in unrelated_queries:
        result = cache.lookup(query)
        assert result is None, f"Expected cache miss for unrelated query: '{query}'"


def test_cache_sub_15ms_latency_sla():
    """Verify roundtrip cache hit latency complies with the <15ms SLA target."""
    mock_client = MockRedisStackClient()
    cache = SemanticCache(client=mock_client)

    prompt = "get_sales_analytics(date_from='2026-01-01', date_to='2026-03-31')"
    cache.set(prompt, {"revenue": 500000.0})

    # Warmup
    cache.lookup(prompt)

    latencies: List[float] = []
    iterations = 20
    for _ in range(iterations):
        t0 = time.perf_counter()
        res = cache.lookup(prompt)
        latencies.append((time.perf_counter() - t0) * 1000.0)
        assert res is not None

    avg_latency = sum(latencies) / len(latencies)
    min_latency = min(latencies)
    max_latency = max(latencies)

    print(
        f"\n  [Semantic Cache SLA Benchmark] Avg: {avg_latency:.2f} ms | "
        f"Min: {min_latency:.2f} ms | Max: {max_latency:.2f} ms (Target: < 15.0 ms)"
    )
    assert avg_latency < 15.0, f"Average latency {avg_latency:.2f} ms exceeded 15.0 ms SLA"


def test_ttl_and_expiration():
    """Verify entries expire and are excluded from vector search when TTL elapses."""
    mock_client = MockRedisStackClient()
    cache = SemanticCache(client=mock_client)

    prompt = "Temporary fast-expiring query"
    cache.set(prompt, {"status": "ephemeral"}, ttl=1)

    # Immediately available
    assert cache.lookup(prompt) is not None

    # Simulate time advancing past TTL
    mock_client.expiries[f"{DOC_PREFIX}{cache.set(prompt, {'status': 'ephemeral'}, ttl=1).replace(DOC_PREFIX, '')}"] = time.time() - 1

    # Should miss cache after expiration
    assert cache.lookup(prompt) is None


def test_clear_and_stats():
    """Verify clear() purges all keys and stats() returns accurate telemetry."""
    mock_client = MockRedisStackClient()
    cache = SemanticCache(client=mock_client)

    cache.set("Query 1", "Response 1")
    cache.set("Query 2", "Response 2")
    cache.set("Query 3", "Response 3")

    assert cache.count() == 3
    stats = cache.stats()
    assert stats["active_entries"] == 3
    assert stats["dimension"] == 384
    assert stats["similarity_threshold"] == 0.94

    cleared = cache.clear()
    assert cleared == 3
    assert cache.count() == 0


def test_in_memory_fallback_resilience():
    """Verify system falls back gracefully when Redis is offline without crashing."""
    cache = SemanticCache(
        redis_url="redis://localhost:6399/99",  # Unused port
        fallback_to_memory=True,
    )
    assert cache.is_memory_fallback is True

    # Validate operations succeed in fallback mode
    cache.set("Fallback prompt", {"status": "ok"})
    hit = cache.lookup("Fallback prompt")
    assert hit is not None
    assert hit["response"] == {"status": "ok"}


if __name__ == "__main__":
    test_functions = [
        test_index_initialization_and_schema,
        test_exact_query_cache_hit,
        test_paraphrased_query_cache_hit,
        test_semantically_distinct_query_miss,
        test_cache_sub_15ms_latency_sla,
        test_ttl_and_expiration,
        test_clear_and_stats,
        test_in_memory_fallback_resilience,
    ]

    print(f"Executing Redis Semantic Cache Test Suite ({len(test_functions)} test suites)...")
    for fn in test_functions:
        fn()
        print(f"  [PASS] {fn.__name__}")

    print("\nALL SEMANTIC CACHE TESTS PASSED!")
