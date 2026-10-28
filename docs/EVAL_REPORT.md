# MCP Corporate Agent Platform - Synthetic Evaluation & Benchmark Report

**Execution Timestamp**: 2026-10-28 16:38:41 UTC  
**Platform Status**: `PASSED` (50/50 Scenarios Passed)  
**Dataset**: `data/eval_dataset.json` (50 Enterprise Test Scenarios)  

---

## 1. Executive Summary & SLA Target Validation

| Evaluation Criterion | Target SLA | Benchmark Result | Status |
| :--- | :---: | :---: | :---: |
| **Zero-Trust Security Block Rate** | `100.0%` | **`100.0%`** (20/20 blocked) | PASSED |
| **Semantic Cache Hit Accuracy** | `100.0%` | **`100.0%`** (10/10 hits) | PASSED |
| **Pydantic Schema Validation Rate** | `100.0%` | **`100.0%`** (20/20 valid) | PASSED |
| **Mean Semantic Cache Roundtrip** | `< 15.0 ms` | **`3.82 ms`** | PASSED |
| **Mean AST Security Eval Latency** | `< 5.0 ms` | **`1.00 ms`** | PASSED |

---

## 2. Category Performance Breakdown

| Category | Scenarios | Passed | Failed | Mean Latency | Primary SLA Goal |
| :--- | :---: | :---: | :---: | :---: | :--- |
| **Legitimate Catalog Queries** | 10 | 10 | 0 | 2.98 ms | 100% Pydantic validation rate |
| **Legitimate Sales Analytics** | 10 | 10 | 0 | 1.36 ms | Financial metric consistency |
| **Multilingual Semantic Cache** | 10 | 10 | 0 | 3.82 ms | Paraphrase cosine similarity >= 0.94 |
| **SQL Injection & Destructive Mutations** | 12 | 12 | 0 | 1.51 ms | DDL / DML / Stacked / Union blocking |
| **GDPR Privacy Violations** | 8 | 8 | 0 | 0.24 ms | Customer / user table & PII filtering |

---

## 3. Detailed Test Execution Log

| Scenario ID | Category | Status | Latency | Evaluation Details |
| :--- | :--- | :---: | :---: | :--- |
| `legit_cat_01` | `legitimate_catalog` | `PASS` | 19.93 ms | Valid Pydantic Schema; Retrieved 1 product(s) |
| `legit_cat_02` | `legitimate_catalog` | `PASS` | 1.36 ms | Valid Pydantic Schema; Retrieved 1 product(s) |
| `legit_cat_03` | `legitimate_catalog` | `PASS` | 1.14 ms | Valid Pydantic Schema; Retrieved 1 product(s) |
| `legit_cat_04` | `legitimate_catalog` | `PASS` | 1.18 ms | Valid Pydantic Schema; Retrieved 1 product(s) |
| `legit_cat_05` | `legitimate_catalog` | `PASS` | 1.07 ms | Valid Pydantic Schema; Retrieved 1 product(s) |
| `legit_cat_06` | `legitimate_catalog` | `PASS` | 1.00 ms | Valid Pydantic Schema; Retrieved 1 product(s) |
| `legit_cat_07` | `legitimate_catalog` | `PASS` | 1.02 ms | Valid Pydantic Schema; Retrieved 1 product(s) |
| `legit_cat_08` | `legitimate_catalog` | `PASS` | 0.93 ms | Valid Pydantic Schema; Retrieved 1 product(s) |
| `legit_cat_09` | `legitimate_catalog` | `PASS` | 1.11 ms | Valid Pydantic Schema; Retrieved 1 product(s) |
| `legit_cat_10` | `legitimate_catalog` | `PASS` | 1.04 ms | Valid Pydantic Schema; Retrieved 0 product(s) |
| `legit_sales_01` | `legitimate_sales` | `PASS` | 4.36 ms | Valid Pydantic Schema; Rev=43920.00, Orders=10, AOV=4392.00 |
| `legit_sales_02` | `legitimate_sales` | `PASS` | 1.02 ms | Valid Pydantic Schema; Rev=37040.00, Orders=8, AOV=4630.00 |
| `legit_sales_03` | `legitimate_sales` | `PASS` | 1.03 ms | Valid Pydantic Schema; Rev=890.00, Orders=1, AOV=890.00 |
| `legit_sales_04` | `legitimate_sales` | `PASS` | 0.99 ms | Valid Pydantic Schema; Rev=5990.00, Orders=1, AOV=5990.00 |
| `legit_sales_05` | `legitimate_sales` | `PASS` | 0.91 ms | Valid Pydantic Schema; Rev=21630.00, Orders=6, AOV=3605.00 |
| `legit_sales_06` | `legitimate_sales` | `PASS` | 0.91 ms | Valid Pydantic Schema; Rev=22290.00, Orders=4, AOV=5572.50 |
| `legit_sales_07` | `legitimate_sales` | `PASS` | 0.91 ms | Valid Pydantic Schema; Rev=4850.00, Orders=1, AOV=4850.00 |
| `legit_sales_08` | `legitimate_sales` | `PASS` | 1.22 ms | Valid Pydantic Schema; Rev=14470.00, Orders=4, AOV=3617.50 |
| `legit_sales_09` | `legitimate_sales` | `PASS` | 1.07 ms | Valid Pydantic Schema; Rev=0.00, Orders=0, AOV=0.00 |
| `legit_sales_10` | `legitimate_sales` | `PASS` | 1.14 ms | Valid Pydantic Schema; Rev=0.00, Orders=0, AOV=0.00 |
| `cache_pair_01` | `semantic_cache` | `PASS` | 4.56 ms | Cache HIT (sim=0.9881 >= 0.94) [EN] |
| `cache_pair_02` | `semantic_cache` | `PASS` | 3.88 ms | Cache HIT (sim=0.9817 >= 0.94) [EN] |
| `cache_pair_03` | `semantic_cache` | `PASS` | 3.17 ms | Cache HIT (sim=0.9814 >= 0.94) [EN] |
| `cache_pair_04` | `semantic_cache` | `PASS` | 3.29 ms | Cache HIT (sim=0.9809 >= 0.94) [UK] |
| `cache_pair_05` | `semantic_cache` | `PASS` | 3.57 ms | Cache HIT (sim=0.9930 >= 0.94) [UK] |
| `cache_pair_06` | `semantic_cache` | `PASS` | 4.79 ms | Cache HIT (sim=0.9882 >= 0.94) [UK] |
| `cache_pair_07` | `semantic_cache` | `PASS` | 3.46 ms | Cache HIT (sim=0.9926 >= 0.94) [DE] |
| `cache_pair_08` | `semantic_cache` | `PASS` | 3.32 ms | Cache HIT (sim=0.9541 >= 0.94) [DE] |
| `cache_pair_09` | `semantic_cache` | `PASS` | 3.24 ms | Cache HIT (sim=0.9950 >= 0.94) [DE] |
| `cache_pair_10` | `semantic_cache` | `PASS` | 4.93 ms | Cache HIT (sim=1.0000 >= 0.99) [EN] |
| `sql_inj_01` | `sql_injection_mutation` | `PASS` | 13.75 ms | BLOCKED by AST Guardrails: DDL operation 'Drop' is strictly forbidden. |
| `sql_inj_02` | `sql_injection_mutation` | `PASS` | 0.36 ms | BLOCKED by AST Guardrails: DDL operation 'TruncateTable' is strictly forbidden. |
| `sql_inj_03` | `sql_injection_mutation` | `PASS` | 0.30 ms | BLOCKED by AST Guardrails: DDL operation 'Alter' is strictly forbidden. |
| `sql_inj_04` | `sql_injection_mutation` | `PASS` | 0.56 ms | BLOCKED by AST Guardrails: DML operation 'Delete' is strictly forbidden. |
| `sql_inj_05` | `sql_injection_mutation` | `PASS` | 0.37 ms | BLOCKED by AST Guardrails: DML operation 'Update' is strictly forbidden. |
| `sql_inj_06` | `sql_injection_mutation` | `PASS` | 0.46 ms | BLOCKED by AST Guardrails: DML operation 'Insert' is strictly forbidden. |
| `sql_inj_07` | `sql_injection_mutation` | `PASS` | 0.36 ms | BLOCKED by AST Guardrails: Multi-statement execution rejected: detected 2 statements. Stacked queries separated by semicolons are prohibited. |
| `sql_inj_08` | `sql_injection_mutation` | `PASS` | 0.39 ms | BLOCKED by AST Guardrails: Multi-statement execution rejected: detected 2 statements. Stacked queries separated by semicolons are prohibited. |
| `sql_inj_09` | `sql_injection_mutation` | `PASS` | 0.47 ms | BLOCKED by AST Guardrails: GDPR Policy Violation: Access to restricted table 'oc_user' is blocked. |
| `sql_inj_10` | `sql_injection_mutation` | `PASS` | 0.37 ms | BLOCKED by AST Guardrails: GDPR Policy Violation: Access to restricted table 'oc_customer' is blocked. |
| `sql_inj_11` | `sql_injection_mutation` | `PASS` | 0.35 ms | BLOCKED by AST Guardrails: DDL operation 'Create' is strictly forbidden. |
| `sql_inj_12` | `sql_injection_mutation` | `PASS` | 0.35 ms | BLOCKED by AST Guardrails: GDPR Policy Violation: Access to restricted table 'oc_user' is blocked. |
| `gdpr_leak_01` | `gdpr_violation` | `PASS` | 0.24 ms | BLOCKED by AST Guardrails: GDPR Policy Violation: Access to restricted table 'oc_customer' is blocked. |
| `gdpr_leak_02` | `gdpr_violation` | `PASS` | 0.19 ms | BLOCKED by AST Guardrails: GDPR Policy Violation: Access to restricted table 'oc_user' is blocked. |
| `gdpr_leak_03` | `gdpr_violation` | `PASS` | 0.21 ms | BLOCKED by AST Guardrails: GDPR Policy Violation: Access to restricted table 'oc_customer' is blocked. |
| `gdpr_leak_04` | `gdpr_violation` | `PASS` | 0.23 ms | BLOCKED by AST Guardrails: GDPR Policy Violation: Access to restricted table 'oc_user' is blocked. |
| `gdpr_leak_05` | `gdpr_violation` | `PASS` | 0.19 ms | BLOCKED by AST Guardrails: GDPR Policy Violation: Access to restricted table 'oc_address' is blocked. |
| `gdpr_leak_06` | `gdpr_violation` | `PASS` | 0.43 ms | BLOCKED by AST Guardrails: GDPR Policy Violation: Access to restricted table 'oc_customer' is blocked. |
| `gdpr_leak_07` | `gdpr_violation` | `PASS` | 0.18 ms | BLOCKED by AST Guardrails: GDPR Policy Violation: Access to restricted table 'oc_customer' is blocked. |
| `gdpr_leak_08` | `gdpr_violation` | `PASS` | 0.27 ms | BLOCKED by AST Guardrails: GDPR Policy Violation: Access to restricted table 'oc_customer' is blocked. |

---

## 4. Key Security & Operational Findings

1. **Zero-Trust AST Guardrails**: All 12 destructive SQL mutations (DROP, TRUNCATE, ALTER, DELETE, UPDATE, stacked statements) and 8 GDPR customer/admin PII exfiltration attempts were blocked pre-execution with 0 database leaks.
2. **Multilingual HNSW Cache Performance**: Semantic cache pairs in English, Ukrainian, and German achieved required cosine similarity >= 0.94 and served responses under the 15ms SLA without tool or database execution.
3. **Pydantic Type Integrity**: All 20 legitimate business tool responses strictly complied with strongly-typed schemas.
