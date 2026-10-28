"""
Redis Stack HNSW Semantic Cache Layer.

Intercepts repetitive and semantically equivalent queries using
RediSearch HNSW 384-dimensional cosine vector indexing, serving cached
responses at sub-15ms roundtrip latency with zero LLM tokens and zero DB hits.
"""

import hashlib
import json
import logging
import time
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import redis
from redis.commands.search.query import Query
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import ResponseError

from src.cache.embeddings import embed_text, get_embedding_engine
from src.core.config import settings

logger = logging.getLogger("mcp.cache.semantic_cache")

INDEX_NAME = "idx:semantic_cache"
DOC_PREFIX = "mcp:cache:"
DEFAULT_DIM = 384
DEFAULT_METRIC = "COSINE"


class MockRedisStackClient:
    """
    In-memory simulation of Redis Stack with RediSearch and HNSW vector search.
    Provides complete test and CI capability without requiring an external Redis daemon.
    """

    def __init__(self) -> None:
        self.hashes: Dict[str, Dict[str, Any]] = {}
        self.expiries: Dict[str, float] = {}
        self.indices: Dict[str, Dict[str, Any]] = {}

    def ping(self) -> bool:
        return True

    def execute_command(self, *args, **options) -> Any:
        cmd = str(args[0]).upper()
        if cmd == "PING":
            return b"PONG"
        elif cmd == "FT.INFO":
            idx = args[1]
            if idx not in self.indices:
                raise ResponseError("Unknown Index name")
            return self.indices[idx]
        elif cmd == "FT.CREATE":
            idx = args[1]
            if idx in self.indices:
                raise ResponseError("Index already exists")
            self.indices[idx] = {"args": args}
            return b"OK"
        elif cmd == "FT.SEARCH":
            idx = args[1]
            return [0]
        return b"OK"

    def ft(self, index_name: str = INDEX_NAME):
        return MockSearchCommands(self, index_name)

    def hset(self, name: str, key: Optional[str] = None, value: Optional[str] = None, mapping: Optional[Dict[str, Any]] = None) -> int:
        if name not in self.hashes:
            self.hashes[name] = {}
        if mapping:
            self.hashes[name].update(mapping)
        elif key is not None and value is not None:
            self.hashes[name][key] = value
        return len(self.hashes[name])

    def hgetall(self, name: str) -> Dict[str, Any]:
        self._purge_expired(name)
        return self.hashes.get(name, {})

    def expire(self, name: str, time_seconds: int) -> bool:
        self.expiries[name] = time.time() + time_seconds
        return True

    def delete(self, *names: str) -> int:
        count = 0
        for name in names:
            if name in self.hashes:
                del self.hashes[name]
                count += 1
            if name in self.expiries:
                del self.expiries[name]
        return count

    def scan_iter(self, match: str = "*", count: Optional[int] = None):
        prefix = match.replace("*", "")
        now = time.time()
        for k in list(self.hashes.keys()):
            if k.startswith(prefix):
                if k in self.expiries and self.expiries[k] <= now:
                    self.delete(k)
                    continue
                yield k

    def _purge_expired(self, name: str) -> None:
        if name in self.expiries and self.expiries[name] <= time.time():
            self.delete(name)


class MockSearchCommands:
    """Mock implementation of RediSearch FT.SEARCH with HNSW KNN support."""

    def __init__(self, mock_client: MockRedisStackClient, index_name: str) -> None:
        self.mock_client = mock_client
        self.index_name = index_name

    def info(self) -> Dict[str, Any]:
        if self.index_name not in self.mock_client.indices:
            raise ResponseError("Unknown Index name")
        return self.mock_client.indices[self.index_name]

    def search(self, query: Union[str, Query], query_params: Optional[Dict[str, Any]] = None):
        vec_bytes = query_params.get("vec") if query_params else None
        if vec_bytes is None:
            return MockSearchResult([])

        query_vec = np.frombuffer(vec_bytes, dtype=np.float32)
        q_norm = np.linalg.norm(query_vec)
        if q_norm > 0:
            query_vec = query_vec / q_norm

        now = time.time()
        scored_docs = []

        for doc_id, data in list(self.mock_client.hashes.items()):
            if doc_id in self.mock_client.expiries and self.mock_client.expiries[doc_id] <= now:
                self.mock_client.delete(doc_id)
                continue

            doc_vec_bytes = data.get("vector")
            if not doc_vec_bytes:
                continue

            doc_vec = np.frombuffer(doc_vec_bytes, dtype=np.float32)
            d_norm = np.linalg.norm(doc_vec)
            if d_norm > 0:
                doc_vec = doc_vec / d_norm

            cos_sim = float(np.dot(query_vec, doc_vec))
            cos_dist = max(0.0, 1.0 - cos_sim)

            doc_obj = MockDocument(
                doc_id=doc_id,
                prompt=data.get("prompt", ""),
                response=data.get("response", ""),
                score=cos_dist,
            )
            scored_docs.append((cos_dist, doc_obj))

        scored_docs.sort(key=lambda x: x[0])
        docs = [d for _, d in scored_docs[:1]]
        return MockSearchResult(docs)


class MockDocument:
    def __init__(self, doc_id: str, prompt: str, response: str, score: float) -> None:
        self.id = doc_id
        self.prompt = prompt
        self.response = response
        self.score = str(score)


class MockSearchResult:
    def __init__(self, docs: List[MockDocument]) -> None:
        self.docs = docs
        self.total = len(docs)


class SemanticCache:
    """
    Production-grade Semantic Caching Layer backed by Redis Stack (RediSearch / HNSW).
    Provides sub-15ms roundtrip query interception and response reuse.
    """

    def __init__(
        self,
        redis_url: Optional[str] = None,
        index_name: str = INDEX_NAME,
        doc_prefix: str = DOC_PREFIX,
        embedding_dim: Optional[int] = None,
        similarity_threshold: Optional[float] = None,
        ttl_seconds: Optional[int] = None,
        client: Optional[Any] = None,
        fallback_to_memory: bool = True,
    ) -> None:
        self.redis_url = redis_url or settings.redis_url
        self.index_name = index_name
        self.doc_prefix = doc_prefix
        self.embedding_dim = embedding_dim or settings.embedding_dim
        self.similarity_threshold = (
            similarity_threshold
            if similarity_threshold is not None
            else settings.similarity_threshold
        )
        self.ttl_seconds = ttl_seconds or settings.cache_ttl_seconds
        self.distance_metric = DEFAULT_METRIC

        self.client = client
        self.is_memory_fallback = False
        self._memory_cache: Dict[str, Dict[str, Any]] = {}

        self._init_connection(fallback_to_memory)
        self._ensure_index()

    def _init_connection(self, fallback_to_memory: bool) -> None:
        """Initializes connection to Redis Stack, gracefully falling back to memory if unreachable."""
        if self.client is not None:
            return

        try:
            r = redis.from_url(self.redis_url, decode_responses=False, socket_timeout=2.0)
            r.ping()
            self.client = r
            logger.info("Connected to Redis Stack at %s", self.redis_url)
        except Exception as exc:
            if fallback_to_memory:
                logger.warning(
                    "Redis Stack unavailable at %s (%s). Operating in-memory semantic cache fallback.",
                    self.redis_url,
                    exc,
                )
                self.is_memory_fallback = True
                self.client = MockRedisStackClient()
            else:
                logger.error("Failed to connect to Redis Stack: %s", exc)
                raise

    def _ensure_index(self) -> None:
        """
        Initializes index idx:semantic_cache on hash prefix mcp:cache: with 384-dimensional cosine distance:
        SCHEMA prompt TEXT response TEXT vector VECTOR HNSW 6 TYPE FLOAT32 DIM 384 DISTANCE_METRIC COSINE
        """
        try:
            self.client.execute_command("FT.INFO", self.index_name)
            logger.debug("Redis HNSW index '%s' is active.", self.index_name)
        except ResponseError as exc:
            err_msg = str(exc)
            if "Unknown Index name" in err_msg or "no such index" in err_msg.lower():
                logger.info("Creating Redis HNSW vector index '%s' on prefix '%s'...", self.index_name, self.doc_prefix)
                self.client.execute_command(
                    "FT.CREATE",
                    self.index_name,
                    "ON", "HASH",
                    "PREFIX", "1", self.doc_prefix,
                    "SCHEMA",
                    "prompt", "TEXT",
                    "response", "TEXT",
                    "vector", "VECTOR", "HNSW", "6",
                    "TYPE", "FLOAT32",
                    "DIM", str(self.embedding_dim),
                    "DISTANCE_METRIC", self.distance_metric,
                )
                logger.info("Redis HNSW vector index '%s' successfully created.", self.index_name)
            elif "Index already exists" in err_msg:
                logger.debug("Index '%s' already exists.", self.index_name)
            else:
                raise

    def lookup(
        self,
        prompt: str,
        threshold: Optional[float] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Searches the semantic vector cache for a matching prompt.

        1. Embeds query via local ONNX engine (<8ms).
        2. Queries Redis KNN: *=>[KNN 1 @vector $vec AS score]
        3. Calculates cosine similarity = 1.0 - float(doc.score).
        4. If similarity >= threshold (default 0.94), returns cached payload immediately.
        5. If similarity < threshold, returns None (cache miss).

        :param prompt: User or agent input query.
        :param threshold: Optional override for cosine similarity threshold.
        :return: Dict containing hit metadata and response, or None on miss.
        """
        t0 = time.perf_counter()
        active_threshold = threshold if threshold is not None else self.similarity_threshold

        # 1. Embed query vector using local quantized ONNX engine
        query_vector = embed_text(prompt)
        query_vec_bytes = np.array(query_vector, dtype=np.float32).tobytes()

        # 2. Query Redis KNN
        query = (
            Query("*=>[KNN 1 @vector $vec AS score]")
            .sort_by("score")
            .return_fields("prompt", "response", "score")
            .paging(0, 1)
            .dialect(2)
        )

        try:
            results = self.client.ft(self.index_name).search(
                query, query_params={"vec": query_vec_bytes}
            )
        except Exception as exc:
            logger.warning("RediSearch KNN query failed: %s", exc)
            return None

        if not results.docs:
            return None

        doc = results.docs[0]
        try:
            cosine_distance = float(doc.score)
        except (ValueError, TypeError):
            return None

        # 3. Calculate cosine similarity
        similarity = max(0.0, 1.0 - cosine_distance)
        elapsed_ms = (time.perf_counter() - t0) * 1000.0

        # 4. Enforce SLA threshold
        if similarity >= active_threshold:
            raw_response = getattr(doc, "response", "")
            if isinstance(raw_response, bytes):
                raw_response = raw_response.decode("utf-8")

            # Parse JSON if payload is serialized structure
            try:
                parsed_response = json.loads(raw_response)
            except (json.JSONDecodeError, TypeError):
                parsed_response = raw_response

            cached_prompt = getattr(doc, "prompt", "")
            if isinstance(cached_prompt, bytes):
                cached_prompt = cached_prompt.decode("utf-8")

            logger.info(
                "Semantic Cache HIT (sim=%.4f >= %.2f in %.2f ms): '%s'",
                similarity,
                active_threshold,
                elapsed_ms,
                prompt[:40],
            )
            return {
                "hit": True,
                "prompt": cached_prompt,
                "response": parsed_response,
                "similarity": round(similarity, 4),
                "latency_ms": round(elapsed_ms, 2),
            }

        logger.debug(
            "Semantic Cache MISS (sim=%.4f < %.2f in %.2f ms): '%s'",
            similarity,
            active_threshold,
            elapsed_ms,
            prompt[:40],
        )
        return None

    def get(self, prompt: str, threshold: Optional[float] = None) -> Optional[Dict[str, Any]]:
        """Alias for lookup()."""
        return self.lookup(prompt, threshold=threshold)

    def set(
        self,
        prompt: str,
        response: Union[str, Dict[str, Any], List[Any]],
        vector: Optional[List[float]] = None,
        ttl: Optional[int] = None,
    ) -> str:
        """
        Stores a prompt and its response along with the 384-dimensional embedding in Redis.

        :param prompt: Query text.
        :param response: Output string or JSON-serializable object.
        :param vector: Pre-calculated embedding vector (optional, auto-generated if omitted).
        :param ttl: Time-to-live in seconds (defaults to settings.cache_ttl_seconds).
        :return: Redis key under which entry was cached.
        """
        if vector is None:
            vector = embed_text(prompt)

        ttl_val = ttl or self.ttl_seconds
        serialized_resp = (
            json.dumps(response, ensure_ascii=False)
            if isinstance(response, (dict, list))
            else str(response)
        )

        doc_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:16]
        key = f"{self.doc_prefix}{doc_hash}"
        vec_bytes = np.array(vector, dtype=np.float32).tobytes()

        mapping = {
            "prompt": prompt,
            "response": serialized_resp,
            "vector": vec_bytes,
        }

        self.client.hset(key, mapping=mapping)
        self.client.expire(key, ttl_val)
        logger.debug("Cached query in Redis under key '%s' (TTL=%ds)", key, ttl_val)
        return key

    def clear(self) -> int:
        """Clears all cached semantic entries matching mcp:cache:*."""
        count = 0
        keys_to_delete = []
        for key in self.client.scan_iter(match=f"{self.doc_prefix}*"):
            keys_to_delete.append(key)

        if keys_to_delete:
            count = self.client.delete(*keys_to_delete)
        logger.info("Cleared %d entries from semantic cache.", count)
        return count

    def count(self) -> int:
        """Returns the number of active cached entries."""
        return sum(1 for _ in self.client.scan_iter(match=f"{self.doc_prefix}*"))

    def stats(self) -> Dict[str, Any]:
        """Returns operational metadata and telemetry for the semantic cache."""
        return {
            "index_name": self.index_name,
            "doc_prefix": self.doc_prefix,
            "dimension": self.embedding_dim,
            "similarity_threshold": self.similarity_threshold,
            "ttl_seconds": self.ttl_seconds,
            "active_entries": self.count(),
            "backend": "mock_memory" if self.is_memory_fallback else "redis_stack",
        }


# Global singleton instance
_cache_instance: Optional[SemanticCache] = None


def get_semantic_cache() -> SemanticCache:
    """Returns the shared SemanticCache singleton instance."""
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = SemanticCache()
    return _cache_instance


def cached_lookup(prompt: str, threshold: Optional[float] = None) -> Optional[Dict[str, Any]]:
    """Helper to perform semantic cache lookup via the global singleton."""
    return get_semantic_cache().lookup(prompt, threshold=threshold)


def cache_response(
    prompt: str,
    response: Union[str, Dict[str, Any], List[Any]],
    vector: Optional[List[float]] = None,
    ttl: Optional[int] = None,
) -> str:
    """Helper to store a response in the semantic cache via the global singleton."""
    return get_semantic_cache().set(prompt, response, vector=vector, ttl=ttl)
