# Architecture Design & Technical Plan

This document details the architectural specifications, component boundaries, and verification criteria for the **MCP Corporate Agent Platform**.

Refer to the main [README.md](../README.md) for the project overview and roadmap.

## Key Design Principles
1. **Zero-Trust SQL Execution**: LLM-generated SQL queries are never executed directly. They must pass through AST parsing with `sqlglot` which strictly forbids DDL, DML, and GDPR-sensitive tables and columns, and forces `LIMIT 100`.
2. **Sub-15ms Local Semantic Cache**: Using dynamic INT8 quantization on `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` via ONNX Runtime on CPU (<8ms), coupled with Redis Stack HNSW cosine vector index ($\ge 0.94$).
3. **High-Availability LiteLLM Gateway**: 3-tier failover (Groq / local vLLM -> OpenAI gpt-4o-mini) with a `MOCK_LLM=true` offline profile for CI testing and Locust benchmarking.
4. **GitOps-First Kubernetes Orchestration**: Local 3-node K3s cluster on `k3d` with declarative Helm charts synchronized via Argo CD.
5. **Full Observability**: Prometheus metrics (cache hits, latency buckets, AST rejections), Grafana dashboards, and Langfuse tracing.
