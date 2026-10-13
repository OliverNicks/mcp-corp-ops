# Step-by-Step Implementation Plan: ML/AI Engineer & MLOps Engineer

This document outlines the step-by-step implementation plan for the **MCP Corporate Agent Platform**, divided into two specialized engineering tracks:
- **Track A: ML / Agentic AI Engineer**
- **Track B: MLOps / Platform Engineer**

---

## 1. Track A: ML / Agentic AI Engineer Track

### Step AI-1: Project Scaffolding & FastMCP Core Protocol
- **Objective**: Establish the Python package structure and FastMCP server foundation.
- **Tasks**:
  1. Define dependencies in `pyproject.toml` (`fastmcp`, `sqlglot`, `onnxruntime`, `tokenizers`, `redis`, `sqlalchemy`, `pydantic`).
  2. Implement `src/server/mcp_server.py` initializing FastMCP server instance (`FastMCP("corporate-agent-platform")`).
  3. Support both `stdio` transport (for Claude Desktop integration) and `sse`/HTTP transport (for containerized deployments).
  4. Create `src/core/config.py` using `pydantic-settings` to load DB URLs, Redis host, similarity threshold, and mode flags.
- **Verification**: `uv run python -m src.server.mcp_server --help` runs without initialization errors.

### Step AI-2: Database Fixtures & Business Tool Logic
- **Objective**: Implement business domain tools for the `best4baby` store schema.
- **Tasks**:
  1. Build `src/core/db.py`: Dual-engine database abstraction supporting MySQL connection pooling and embedded SQLite test fixtures.
  2. Create SQLite fixture generator `data/fixtures/seed_sqlite.py` with mock data for `oc_product`, `oc_product_option_value`, `oc_order`, `oc_order_product`, `oc_customer`, `oc_user`.
  3. Implement `src/server/tools/catalog_tool.py`:
     - Tool `get_product_stock_levels(product_id: Optional[int], sku: Optional[str])`: Joins `oc_product` and `oc_product_option_value` to return stock counts across variations.
  4. Implement `src/server/tools/sales_tool.py`:
     - Tool `get_sales_analytics(date_from: str, date_to: str, status_id: Optional[int])`: Aggregates gross revenue, order volume, and average order value (AOV) from `oc_order`.
  5. Define strict Pydantic schemas in `src/security/schemas.py` for input parameters and structured JSON responses.
- **Verification**: `uv run pytest tests/test_mcp_tools.py -v` verifies tool outputs against seeded test database records.

### Step AI-3: AST SQL Security Sandbox Guardrails (`sqlglot`)
- **Objective**: Zero-trust AST-level query validation preventing DDL/DML mutation, GDPR leaks, and unconstrained table scans.
- **Tasks**:
  1. Implement `src/security/ast_guardrails.py` using `sqlglot.parse_one(query, read="mysql")`.
  2. **Statement Operation Inspection**:
     - Inspect root expression and all AST branches.
     - Reject query immediately if any node matches: `exp.Insert`, `exp.Update`, `exp.Delete`, `exp.Drop`, `exp.Alter`, `exp.Create`, `exp.Truncate`, `exp.Command`, `exp.Transaction`.
     - Block stacked/multiple SQL statements separated by semicolons.
  3. **GDPR & Privacy Access Control**:
     - Walk all `exp.Table` nodes: reject queries referencing `oc_customer`, `oc_user`, `customer`, `user`, `admin`.
     - Walk all `exp.Column` nodes: reject queries referencing `telephone`, `email`, `password`, `salt`, `token`, `ip`, `card_num`.
     - Reject wildcard `SELECT *` if joining customer-related or restricted tables.
  4. **On-the-Fly AST Mutation**:
     - Inspect AST for `exp.Limit`.
     - If no limit exists, inject `LIMIT 100`.
     - If an existing limit exceeds 100, mutate the node value to 100.
     - Generate sanitized safe SQL: `ast.sql(dialect="mysql")`.
  5. Implement `src/server/tools/sql_tool.py`: `execute_safe_query(query: str, query_purpose: str)` orchestrating AST validation $\to$ execution.
- **Verification**: `uv run pytest tests/test_ast_guardrails.py -v` executes 30+ injection, DDL, GDPR, and LIMIT test cases with 100% block rate.

### Step AI-4: Local Quantized ONNX Embedding Engine (Sub-8ms CPU)
- **Objective**: Run local multilingual vector embeddings entirely on CPU without GPU overhead or cloud latency.
- **Tasks**:
  1. Implement `scripts/export_onnx_model.py`:
     - Download `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` (384 dimensions).
     - Export PyTorch graph to ONNX format.
     - Apply dynamic INT8 quantization (`onnxruntime.quantization.quantize_dynamic`) optimized for CPU execution.
     - Save quantized model to `models/embedding_quantized.onnx` and tokenizer to `models/tokenizer.json`.
  2. Implement `src/cache/embeddings.py`:
     - Load ONNX session using `onnxruntime.InferenceSession` with `CPUExecutionProvider`.
     - Configure thread pool (`intra_op_num_threads`) for optimal CPU core utilization.
     - Fast Rust tokenization, mean pooling over token embeddings, and L2 normalization.
- **Verification**: `uv run pytest tests/test_embeddings.py -v` asserts embedding output dimension is 384 and CPU latency is strictly $<8$ ms.

### Step AI-5: Redis HNSW Semantic Cache Layer (Sub-15ms Roundtrip)
- **Objective**: Intercept repetitive queries and serve cached responses at sub-15ms latency with zero LLM tokens and zero DB hits.
- **Tasks**:
  1. Implement `src/cache/semantic_cache.py`:
     - Connect to Redis Stack (RediSearch / HNSW).
     - Initialize index `idx:semantic_cache` on hash prefix `mcp:cache:` with 384-dimensional cosine distance:
       ```text
       SCHEMA prompt TEXT response TEXT vector VECTOR HNSW 6 TYPE FLOAT32 DIM 384 DISTANCE_METRIC COSINE
       ```
  2. **Lookup Flow**:
     - Embed query via ONNX engine ($<8$ ms).
     - Query Redis KNN: `*=>[KNN 1 @vector $vec AS score]`.
     - Calculate cosine similarity: `similarity = 1.0 - float(doc.score)`.
     - If `similarity >= 0.94`: Return cached JSON payload immediately. Total roundtrip: 10–14 ms.
     - If `similarity < 0.94`: Pass to tool/DB execution, cache the query + vector + result with TTL (default 86400s).
- **Verification**: `uv run pytest tests/test_semantic_cache.py -v` verifies exact matches and paraphrased questions hit cache, while semantically distinct questions miss cache.

### Step AI-6: Synthetic Evaluation Suite & Benchmarking
- **Objective**: Ensure agent response accuracy, security robustness, and cache efficiency over a comprehensive benchmark dataset.
- **Tasks**:
  1. Construct `data/eval_dataset.json` containing 50+ enterprise test scenarios:
     - 20 legitimate catalog and sales analytics queries.
     - 10 semantic cache pairs (paraphrased in English, Ukrainian, and German).
     - 12 SQL injection & destructive mutation attempts (DROP, UPDATE, UNION-based exfiltration).
     - 8 GDPR privacy violations (reading `oc_customer`, `oc_user`, passwords, emails).
  2. Implement `tests/eval_suite.py`:
     - Automated test runner executing all queries against the MCP server.
     - Evaluates 100% Security Block Rate, Cache Hit Accuracy, and Pydantic validation rate.
- **Verification**: `uv run python tests/eval_suite.py` produces a structured markdown report validating all benchmark criteria.

---

## 2. Track B: MLOps / Platform Engineer Track

### Step Ops-1: LiteLLM Gateway & Failover Serving
- **Objective**: Deploy LiteLLM proxy as the high-availability ingress router for model inference.
- **Tasks**:
  1. Create `configs/litellm_config.yaml`:
     - **Primary**: `groq/llama-3.3-70b-versatile` (or local vLLM/Ollama instance).
     - **Critical Fallback**: `openai/gpt-4o-mini`.
     - Routing policy: `latency-based-routing`, timeout `2.5s`, `allowed_fails: 2`, `cooldown_time: 30s`.
  2. Implement configurable `MOCK_LLM=true` profile in `configs/litellm_config.yaml` and `.env`:
     - Offline mock provider endpoint simulating realistic inference latencies, 2.5s timeouts, and 500 error failover for CI/CD runs and load tests without burning API credits.
  3. Implement `src/gateway/litellm_client.py`: Python wrapper handling failover retries and error propagation.
- **Verification**: Simulate primary provider failure (timeout/500) and verify LiteLLM seamlessly routes request to fallback provider within SLA.

### Step Ops-2: Dockerized Development Environment
- **Objective**: One-command local stack for all platform services.
- **Tasks**:
  1. Create `data/fixtures/init_best4baby.sql`: Pre-seeded MySQL database schema and mock records.
  2. Implement `deploy/docker-compose.yml` defining services:
     - `mcp-server`: FastMCP Python application.
     - `redis-stack`: Redis with RediSearch and RedisJSON modules.
     - `mysql-db`: MySQL 8.0 initialized with `init_best4baby.sql`.
     - `litellm`: LiteLLM proxy container mounting `litellm_config.yaml`.
     - `prometheus`: Scrapes metrics from MCP server and LiteLLM.
     - `grafana`: Pre-loaded with operational dashboards.
     - `langfuse`: Tracing service for LLM spans and token auditing.
  3. Create `.env.example` with documented environment variable keys.
- **Verification**: `docker compose config` validates compose syntax cleanly.

### Step Ops-3: Multi-Node K3s Cluster Setup via `k3d`
- **Objective**: Simulate a realistic production Kubernetes topology locally.
- **Tasks**:
  1. Create `deploy/k8s/k3d-cluster.yaml`:
     - 1 control-plane server node.
     - 2 worker/agent nodes.
     - Ingress port forward mappings (`80:80`, `443:443`).
  2. Write automation bootstrap script `scripts/setup_cluster.ps1` (and `setup_cluster.sh`):
     - Installs/checks `k3d` and `kubectl`.
     - Provisions the 3-node cluster: `k3d cluster create --config deploy/k8s/k3d-cluster.yaml`.
     - Installs Argo CD in namespace `argocd`.
- **Verification**: `kubectl get nodes -o wide` displays 1 server and 2 agent nodes in `Ready` state.

### Step Ops-4: Production Helm Chart Architecture
- **Objective**: Package the entire corporate platform into declarative Helm templates.
- **Tasks**:
  1. Scaffold `deploy/k8s/helm/mcp-platform/`:
     - `Chart.yaml`: Chart metadata and versioning.
     - `values.yaml`: Default production values (resource requests, limits, replicas).
     - `values-k3d.yaml`: Local developer overrides (NodePort, smaller resource limits).
  2. Implement template manifests:
     - `templates/mcp-server.yaml`: Deployment with liveness/readiness probes, HPA (Horizontal Pod Autoscaler: 70% CPU target, 2–10 replicas).
     - `templates/litellm.yaml`: Deployment for LiteLLM gateway with ConfigMap mount.
     - `templates/redis.yaml`: StatefulSet with PersistentVolumeClaim for Redis Stack.
     - `templates/mysql.yaml`: Deployment for MySQL with volume persistence and seed ConfigMap.
     - `templates/ingress.yaml`: Ingress routing rules for MCP server, LiteLLM, and dashboards.
     - `templates/service-monitors.yaml`: Prometheus scrape configurations.
- **Verification**: `helm lint deploy/k8s/helm/mcp-platform` and `helm template test deploy/k8s/helm/mcp-platform -f deploy/k8s/helm/mcp-platform/values-k3d.yaml` render without errors.

### Step Ops-5: GitOps Reconciliation with Argo CD
- **Objective**: Automate cluster deployment and continuous synchronization via GitOps.
- **Tasks**:
  1. Create `deploy/k8s/argocd/application.yaml`:
     - Application CRD pointing to git repository `https://github.com/OliverNicks/mcp-corp-ops.git`.
     - Target revision: `mcp_corporate_agent_platform` (or `main`).
     - Target path: `deploy/k8s/helm/mcp-platform`.
     - Destination namespace: `mcp-platform`.
     - Sync policy: Automated with `prune: true` and `selfHeal: true`.
- **Verification**: `kubectl apply -f deploy/k8s/argocd/application.yaml` registers the application in Argo CD, showing `Synced` and `Healthy`.

### Step Ops-6: Telemetry & Dashboards (Prometheus + Grafana)
- **Objective**: Real-time visibility into cache hit ratios, latency buckets, and guardrail blocks.
- **Tasks**:
  1. Implement `src/core/telemetry.py` using `prometheus_client`:
     - `mcp_cache_hits_total` (counter)
     - `mcp_cache_misses_total` (counter)
     - `mcp_cache_hit_ratio` (gauge calculated continuously)
     - `mcp_request_duration_seconds` (histogram with sub-10ms buckets)
     - `mcp_sql_guardrail_rejections_total` (counter partitioned by reason: `dml_blocked`, `gdpr_table_blocked`, `gdpr_column_blocked`)
  2. Create `configs/prometheus.yml` scrape configuration targeting the FastMCP metrics endpoint.
  3. Build `dashboards/grafana/mcp_platform_dashboard.json`:
     - Panel 1: Cache Hit Ratio Gauge (target: $>60\%$ under steady traffic).
     - Panel 2: Total RPS and Ingress Traffic.
     - Panel 3: p50 / p95 / p99 Latency graph (highlighting $<15$ ms cache hits vs $>1.5$ s misses).
     - Panel 4: AST Guardrail Rejection rate and violation breakdown.
     - Panel 5: LiteLLM provider status and failover distribution.
- **Verification**: Prometheus scrapes `/metrics` and Grafana panels populate with simulated traffic.

### Step Ops-7: Full LLM Observability & Tracing with Langfuse
- **Objective**: Comprehensive audit trail of LLM tokens, step latencies, tool execution spans, and costs.
- **Tasks**:
  1. Integrate Langfuse Python SDK in `src/core/telemetry.py` and FastMCP tool wrappers.
  2. Decorate tool calls (`get_product_stock_levels`, `get_sales_analytics`, `execute_safe_query`) with Langfuse spans.
  3. Log input prompt, generated SQL, AST sanitization outcome, model tokens consumed, and execution duration.
- **Verification**: Trigger MCP queries and verify complete trace trees in Langfuse UI.

### Step Ops-8: CI/CD Pipelines & Prompt Regression Testing
- **Objective**: Enforce code quality, security checks, and prompt evaluation before merging code.
- **Tasks**:
  1. Implement `.github/workflows/ci.yml`:
     - Linting and format checks (`ruff check`, `ruff format --check`).
     - Type checking (`mypy`).
     - Unit tests for AST guardrails, ONNX embeddings, and Pydantic schemas.
     - Helm chart validation (`helm lint`).
  2. Implement `.github/workflows/eval_prompt_ci.yml`:
     - Automated regression pipeline running `tests/eval_suite.py` against `data/eval_dataset.json` in `MOCK_LLM=true` mode.
     - PR check fails if Security Block Rate $< 100\%$ or if prompt accuracy regresses.
- **Verification**: Workflows run cleanly on push and pull requests on GitHub.

### Step Ops-9: Concurrency & Stress Testing via Locust
- **Objective**: Validate platform performance and cache efficiency under high concurrency.
- **Tasks**:
  1. Implement `locustfile.py`:
     - Simulates 50 concurrent business analysts issuing queries (mix of repeat stock queries, new analytics, and complex joins).
     - Verifies Redis HNSW connection pooling under high concurrency.
     - Measures p95 and p99 latency degradation under load.
- **Verification**: Run `uv run locust -f locustfile.py --headless -u 50 -r 5 --run-time 1m` and verify zero dropped requests with sub-15ms p95 latency on cached queries.

---

## 3. Collaborative Timeline Matrix (Weeks 1–8)

| Phase | ML / Agentic AI Engineer | MLOps / Platform Engineer | Joint Milestone Output |
| :--- | :--- | :--- | :--- |
| **Weeks 1–2** | • Setup FastMCP server core<br/>• Build `best4baby` store tools (`catalog_tool.py`, `sales_tool.py`)<br/>• Seed SQLite test fixtures | • Setup `docker-compose.yml`<br/>• Seed MySQL DB container with `init_best4baby.sql`<br/>• Scaffold project repo & CI linter | **Working Local Prototype**: FastMCP server successfully queries store databases. |
| **Weeks 3–4** | • Implement `sqlglot` AST security sandbox<br/>• Export & quantize ONNX INT8 embedding model<br/>• Implement Redis HNSW semantic cache | • Configure LiteLLM gateway with failover & mock profile<br/>• Deploy Redis Stack container<br/>• Implement LiteLLM client wrapper | **Secured & Accelerated Engine**: $<15$ms cache hits and 100% blocked SQL injection / GDPR leaks. |
| **Weeks 5–6** | • Create 50+ query evaluation dataset (`eval_dataset.json`)<br/>• Build `eval_suite.py` benchmark runner | • Implement Prometheus exporter & Grafana dashboard<br/>• Integrate Langfuse tracing<br/>• Setup `k3d` 3-node cluster & Helm charts<br/>• Configure Argo CD GitOps sync | **Observable & GitOps-Ready Platform**: Argo CD manages K3s cluster; Grafana & Langfuse trace requests. |
| **Weeks 7–8** | • Run evaluation benchmarks<br/>• Build Claude Desktop integration config (`claude_desktop_config.json`)<br/>• Document architecture and tool specifications | • Run Locust 50-user concurrency stress test<br/>• Finalize GitHub Actions CI prompt regression pipeline<br/>• Polish documentation & deployment guides | **Production-Grade Delivery**: Fully tested, benchmarked, and ready for deployment. |
