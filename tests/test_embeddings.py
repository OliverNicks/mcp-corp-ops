"""
Unit and Latency Test Suite for Local Quantized ONNX Embedding Engine.
Verifies:
- 384-dimensional output embeddings
- Strict L2 unit-norm property (||v|| = 1.0)
- Sub-8ms CPU latency SLA
- Multilingual semantic similarity (English, Ukrainian, German paraphrases >= 0.85, dissimilar < 0.35)
- Edge-case handling (empty string, whitespace, empty batches)
- Error handling for invalid model/tokenizer file paths

Supports both pytest runner and direct execution (`python tests/test_embeddings.py`).
"""

import math
import time
from typing import List

from src.cache.embeddings import (
    EmbeddingEngine,
    embed_batch,
    embed_text,
    get_embedding_engine,
)


def test_embedding_dimension_and_types():
    """Verify that embed_text returns a list of 384 finite floats."""
    text = "What are the stock levels for product 42?"
    vector = embed_text(text)

    assert isinstance(vector, list)
    assert len(vector) == 384, f"Expected 384 dimensions, got {len(vector)}"
    assert all(isinstance(x, float) for x in vector)
    assert all(math.isfinite(x) for x in vector)


def test_embedding_unit_norm():
    """Verify that output vectors are strictly L2-normalized (length = 1.0)."""
    text = "Huppa Avery winter overall waterproof membrane"
    vector = embed_text(text)

    l2_norm = math.sqrt(sum(x * x for x in vector))
    assert abs(l2_norm - 1.0) < 1e-4, f"Vector norm {l2_norm} differs from 1.0"


def test_batch_embedding_consistency():
    """Verify batch embedding produces identical results to individual embeddings."""
    texts = [
        "What are the sales figures for last week?",
        "Check stock levels for product 100",
        "How many orders were placed yesterday?",
    ]
    batch_vectors = embed_batch(texts)

    assert len(batch_vectors) == 3
    for vec in batch_vectors:
        assert len(vec) == 384
        l2_norm = math.sqrt(sum(x * x for x in vec))
        assert abs(l2_norm - 1.0) < 1e-4

    # Compare batch vs individual embed (cosine similarity >= 0.99 accounting for INT8 dynamic quantization scales)
    for idx, text in enumerate(texts):
        single_vec = embed_text(text)
        batch_vec = batch_vectors[idx]
        sim = get_embedding_engine().cosine_similarity(single_vec, batch_vec)
        assert sim >= 0.99, f"Batch and single embed cosine similarity {sim:.4f} < 0.99 for '{text}'"


def test_cpu_latency_sla():
    """
    Verify single-query CPU inference latency meets the SLA requirement:
    Average latency across 20 iterations must be strictly < 8.0 ms.
    """
    engine = get_embedding_engine()
    test_query = "What is the total gross revenue between 2026-01-01 and 2026-03-31?"

    # Warmup runs (3 iterations)
    for _ in range(3):
        engine.embed_text(test_query)

    # Benchmark 20 iterations
    latencies: List[float] = []
    iterations = 20
    for _ in range(iterations):
        t0 = time.perf_counter()
        _ = engine.embed_text(test_query)
        latencies.append((time.perf_counter() - t0) * 1000.0)

    avg_latency = sum(latencies) / len(latencies)
    min_latency = min(latencies)
    max_latency = max(latencies)

    print(
        f"\n  [Latency Benchmark] Avg: {avg_latency:.2f} ms | "
        f"Min: {min_latency:.2f} ms | Max: {max_latency:.2f} ms (Target: < 8.0 ms)"
    )
    assert avg_latency < 8.0, f"Average CPU latency {avg_latency:.2f} ms exceeded 8.0 ms SLA"


def test_multilingual_semantic_similarity():
    """
    Verify high cosine similarity between multilingual paraphrases,
    and low similarity against semantically unrelated sentences.
    """
    engine = get_embedding_engine()

    base_en = "What are the sales figures for last week?"
    paraphrase_en = "Show me the sales data for the past week"
    paraphrase_uk = "Які продажі були за минулий тиждень?"
    paraphrase_de = "Wie hoch waren die Verkaufszahlen der letzten Woche?"
    unrelated = "How to bake a chocolate cake recipe with vanilla extract?"

    v_base = engine.embed_text(base_en)
    v_para_en = engine.embed_text(paraphrase_en)
    v_para_uk = engine.embed_text(paraphrase_uk)
    v_para_de = engine.embed_text(paraphrase_de)
    v_unrelated = engine.embed_text(unrelated)

    sim_en = engine.cosine_similarity(v_base, v_para_en)
    sim_uk = engine.cosine_similarity(v_base, v_para_uk)
    sim_de = engine.cosine_similarity(v_base, v_para_de)
    sim_unrelated = engine.cosine_similarity(v_base, v_unrelated)

    print("\n  [Semantic Similarities]:")
    print(f"    - Base vs EN Paraphrase: {sim_en:.4f} (Expected: >= 0.85)")
    print(f"    - Base vs UK Paraphrase: {sim_uk:.4f} (Expected: >= 0.85)")
    print(f"    - Base vs DE Paraphrase: {sim_de:.4f} (Expected: >= 0.85)")
    print(f"    - Base vs Unrelated:     {sim_unrelated:.4f} (Expected: < 0.35)")

    assert sim_en >= 0.85, f"EN paraphrase similarity {sim_en:.4f} < 0.85"
    assert sim_uk >= 0.85, f"UK paraphrase similarity {sim_uk:.4f} < 0.85"
    assert sim_de >= 0.85, f"DE paraphrase similarity {sim_de:.4f} < 0.85"
    assert sim_unrelated < 0.35, f"Unrelated similarity {sim_unrelated:.4f} >= 0.35"


def test_edge_cases():
    """Verify handling of empty string, whitespace, and empty batch."""
    engine = get_embedding_engine()

    # Empty string
    v_empty = engine.embed_text("")
    assert len(v_empty) == 384
    assert abs(math.sqrt(sum(x * x for x in v_empty)) - 1.0) < 1e-4

    # Whitespace
    v_ws = engine.embed_text("   \t\n  ")
    assert len(v_ws) == 384

    # Empty batch
    assert engine.embed_batch([]) == []


def test_invalid_paths_raise_filenotfound():
    """Verify descriptive FileNotFoundError when model or tokenizer is missing."""
    caught_model = False
    try:
        EmbeddingEngine(model_path="models/nonexistent_model.onnx")
    except FileNotFoundError as e:
        caught_model = True
        assert "Quantized ONNX model file not found" in str(e)
    assert caught_model, "Expected FileNotFoundError for nonexistent model"

    caught_tok = False
    try:
        EmbeddingEngine(
            model_path="models/embedding_quantized.onnx",
            tokenizer_path="models/nonexistent_tokenizer.json",
        )
    except FileNotFoundError as e:
        caught_tok = True
        assert "Fast Tokenizer configuration file not found" in str(e)
    assert caught_tok, "Expected FileNotFoundError for nonexistent tokenizer"


if __name__ == "__main__":
    test_functions = [
        test_embedding_dimension_and_types,
        test_embedding_unit_norm,
        test_batch_embedding_consistency,
        test_cpu_latency_sla,
        test_multilingual_semantic_similarity,
        test_edge_cases,
        test_invalid_paths_raise_filenotfound,
    ]

    print(f"Executing Embedding Engine Test Suite ({len(test_functions)} test suites)...")
    for fn in test_functions:
        fn()
        print(f"  [PASS] {fn.__name__}")

    print("\nALL EMBEDDING ENGINE TESTS PASSED!")
