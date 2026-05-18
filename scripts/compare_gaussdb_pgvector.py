"""Compare mem0 GaussDB and pgvector providers on the same synthetic workload.

This script intentionally works at the mem0 vector-store provider layer rather
than calling an external LLM. It uses deterministic vectors, payloads, filters,
and queries so differences come from the database/provider behavior.

Environment variables:
  GaussDB:
    GAUSSDB_HOST, GAUSSDB_PORT, GAUSSDB_DATABASE, GAUSSDB_USER, GAUSSDB_PASSWORD
    or the GAUSSDB_TEST_* variants used by live tests.
    Optional: GAUSSDB_EVAL_DEPLOYMENT_MODE=distributed, GAUSSDB_EVAL_DISTRIBUTION_MODE=auto.

  pgvector:
    PGVECTOR_HOST, PGVECTOR_PORT, PGVECTOR_DATABASE, PGVECTOR_USER, PGVECTOR_PASSWORD

Example local pgvector container:
  docker run -d --name mem0-pgvector-eval \
    -e POSTGRES_USER=mem0 -e POSTGRES_PASSWORD=mem0pass -e POSTGRES_DB=mem0_eval \
    -p 15432:5432 pgvector/pgvector:pg16

Example run:
  python scripts/compare_gaussdb_pgvector.py --provider both --scenario complex --scale 4
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import time
import uuid
from dataclasses import dataclass
from typing import Any

from mem0.vector_stores.base import VectorStoreBase
from mem0.vector_stores.gaussdb import GaussDB
from mem0.vector_stores.pgvector import PGVector


DIMENSIONS = 8
RUN_ID = "mem0-provider-ab-run"


@dataclass(frozen=True)
class MemoryCase:
    key: str
    data: str
    text_lemmatized: str
    user_id: str
    agent_id: str
    category: str
    language: str
    vector: list[float]

    @property
    def id(self) -> str:
        return str(uuid.uuid5(uuid.NAMESPACE_URL, f"mem0-provider-ab/{self.key}"))

    @property
    def payload(self) -> dict[str, Any]:
        return {
            "data": self.data,
            "text_lemmatized": self.text_lemmatized,
            "user_id": self.user_id,
            "agent_id": self.agent_id,
            "run_id": RUN_ID,
            "category": self.category,
            "language": self.language,
        }


@dataclass(frozen=True)
class QueryCase:
    name: str
    text: str
    vector: list[float]
    keyword_query: str
    filters: dict[str, Any]
    expected_key: str
    expected_id: str


def _env(*names: str, default: str | None = None) -> str | None:
    for name in names:
        value = os.getenv(name)
        if value:
            return value
    return default


def _require_env(*names: str) -> str:
    value = _env(*names)
    if value is None:
        raise RuntimeError(f"Missing environment variable. Provide one of: {', '.join(names)}")
    return value


def _offset(vector: list[float], amount: float) -> list[float]:
    return [round(value + amount, 4) for value in vector]


def build_simple_dataset(scale: int) -> list[MemoryCase]:
    base_cases = [
        MemoryCase(
            key="travel-window-seat",
            data="Alice prefers quiet window seats on morning flights",
            text_lemmatized="alice prefer quiet window seat morning flight",
            user_id="alice",
            agent_id="travel-agent",
            category="travel",
            language="en",
            vector=[0.91, 0.12, 0.10, 0.05, 0.02, 0.01, 0.03, 0.04],
        ),
        MemoryCase(
            key="travel-boarding",
            data="小李 books flights with priority boarding",
            text_lemmatized="小李 book flight priority boarding",
            user_id="xiaoli",
            agent_id="travel-agent",
            category="travel",
            language="mixed",
            vector=[0.88, 0.15, 0.12, 0.07, 0.03, 0.01, 0.02, 0.05],
        ),
        MemoryCase(
            key="food-coffee-cn",
            data="小王喜欢早晨喝拿铁咖啡",
            text_lemmatized="小王 喜欢 早晨 喝 拿铁 咖啡",
            user_id="xiaowang",
            agent_id="food-agent",
            category="food",
            language="zh",
            vector=[0.10, 0.89, 0.12, 0.05, 0.03, 0.06, 0.04, 0.01],
        ),
        MemoryCase(
            key="food-vegetarian",
            data="Carol prefers vegetarian lunch and jasmine tea",
            text_lemmatized="carol prefer vegetarian lunch jasmine tea",
            user_id="carol",
            agent_id="food-agent",
            category="food",
            language="en",
            vector=[0.11, 0.86, 0.16, 0.04, 0.05, 0.04, 0.03, 0.02],
        ),
        MemoryCase(
            key="finance-invoice",
            data="Dana tracks invoice approvals before quarterly reporting",
            text_lemmatized="dana track invoice approval quarterly reporting",
            user_id="dana",
            agent_id="finance-agent",
            category="finance",
            language="en",
            vector=[0.08, 0.05, 0.91, 0.10, 0.02, 0.03, 0.02, 0.04],
        ),
        MemoryCase(
            key="health-running",
            data="Evan runs five kilometers after work on Wednesdays",
            text_lemmatized="evan run five kilometer after work wednesday",
            user_id="evan",
            agent_id="health-agent",
            category="health",
            language="en",
            vector=[0.03, 0.05, 0.09, 0.90, 0.12, 0.04, 0.02, 0.02],
        ),
    ]

    records: list[MemoryCase] = []
    for repeat in range(scale):
        for case in base_cases:
            if repeat == 0:
                records.append(case)
                continue
            records.append(
                MemoryCase(
                    key=f"{case.key}-{repeat}",
                    data=f"{case.data} variant {repeat}",
                    text_lemmatized=f"{case.text_lemmatized} variant {repeat}",
                    user_id=case.user_id,
                    agent_id=case.agent_id,
                    category=case.category,
                    language=case.language,
                    vector=_offset(case.vector, repeat * 0.0003),
                )
            )
    return records


def build_simple_queries(records: list[MemoryCase]) -> list[QueryCase]:
    by_key = {record.key: record for record in records}
    targets = [
        ("travel_window", "flight seat preference", "window seat", "travel-window-seat"),
        ("travel_priority", "priority boarding flight", "priority boarding", "travel-boarding"),
        ("zh_coffee", "早晨饮品偏好", "拿铁 咖啡", "food-coffee-cn"),
        ("food_lunch", "meal preference", "vegetarian lunch", "food-vegetarian"),
        ("finance_invoice", "invoice approval reporting", "invoice approval", "finance-invoice"),
        ("health_running", "running habit", "five kilometer", "health-running"),
    ]
    return [
        QueryCase(
            name=name,
            text=text,
            vector=by_key[key].vector,
            keyword_query=keyword,
            filters={"user_id": by_key[key].user_id},
            expected_key=key,
            expected_id=by_key[key].id,
        )
        for name, text, keyword, key in targets
    ]


def build_complex_dataset(scale: int) -> list[MemoryCase]:
    base_cases = [
        MemoryCase(
            key="alice-window-seat",
            data="Alice strongly prefers quiet window seats on early morning flights",
            text_lemmatized="alice strongly prefer quiet window seat early morning flight",
            user_id="alice",
            agent_id="travel-agent",
            category="travel",
            language="en",
            vector=[0.90, 0.12, 0.05, 0.05, 0.02, 0.02, 0.01, 0.01],
        ),
        MemoryCase(
            key="alice-aisle-seat-negative",
            data="Alice dislikes aisle seats unless the flight is overnight",
            text_lemmatized="alice dislike aisle seat unless flight overnight",
            user_id="alice",
            agent_id="travel-agent",
            category="travel",
            language="en",
            vector=[0.91, 0.13, 0.05, 0.05, 0.02, 0.02, 0.01, 0.01],
        ),
        MemoryCase(
            key="bob-window-cross-tenant",
            data="Bob prefers quiet window seats on morning flights",
            text_lemmatized="bob prefer quiet window seat morning flight",
            user_id="bob",
            agent_id="travel-agent",
            category="travel",
            language="en",
            vector=[0.90, 0.12, 0.05, 0.05, 0.02, 0.02, 0.01, 0.01],
        ),
        MemoryCase(
            key="xiaoli-priority-boarding",
            data="小李 books flights with priority boarding and upgrade coupons",
            text_lemmatized="小李 book flight priority boarding upgrade coupon",
            user_id="xiaoli",
            agent_id="travel-agent",
            category="travel",
            language="mixed",
            vector=[0.87, 0.16, 0.06, 0.06, 0.02, 0.02, 0.02, 0.02],
        ),
        MemoryCase(
            key="xiaowang-latte",
            data="小王喜欢早晨喝拿铁咖啡",
            text_lemmatized="小王 喜欢 早晨 喝 拿铁 咖啡 latte coffee",
            user_id="xiaowang",
            agent_id="food-agent",
            category="food",
            language="zh",
            vector=[0.10, 0.90, 0.05, 0.04, 0.05, 0.02, 0.02, 0.02],
        ),
        MemoryCase(
            key="xiaowang-matcha-negative",
            data="小王周末会点抹茶蛋糕但不喝咖啡",
            text_lemmatized="小王 weekend order matcha cake not coffee",
            user_id="xiaowang",
            agent_id="food-agent",
            category="food",
            language="zh",
            vector=[0.11, 0.89, 0.05, 0.04, 0.05, 0.02, 0.02, 0.02],
        ),
        MemoryCase(
            key="dana-2fa-reset",
            data="Dana needs help resetting two factor authentication for the finance portal",
            text_lemmatized="dana need help reset two factor authentication 2fa finance portal authenticator",
            user_id="dana",
            agent_id="support-agent",
            category="support",
            language="en",
            vector=[0.05, 0.04, 0.10, 0.90, 0.06, 0.03, 0.02, 0.02],
        ),
        MemoryCase(
            key="dana-password-reset-negative",
            data="Dana changed her finance portal password last month",
            text_lemmatized="dana change finance portal password last month",
            user_id="dana",
            agent_id="support-agent",
            category="support",
            language="en",
            vector=[0.05, 0.04, 0.10, 0.91, 0.06, 0.03, 0.02, 0.02],
        ),
        MemoryCase(
            key="carol-invoice-approval",
            data="Carol tracks invoice approvals before quarterly reporting",
            text_lemmatized="carol track invoice approval quarterly reporting",
            user_id="carol",
            agent_id="finance-agent",
            category="finance",
            language="en",
            vector=[0.04, 0.05, 0.91, 0.08, 0.05, 0.03, 0.02, 0.02],
        ),
        MemoryCase(
            key="carol-reimbursement-negative",
            data="Carol files travel reimbursements after conferences",
            text_lemmatized="carol file travel reimbursement conference",
            user_id="carol",
            agent_id="finance-agent",
            category="finance",
            language="en",
            vector=[0.05, 0.05, 0.90, 0.08, 0.05, 0.03, 0.02, 0.02],
        ),
        MemoryCase(
            key="evan-running-wednesday",
            data="Evan runs five kilometers after work every Wednesday",
            text_lemmatized="evan run five kilometer after work every wednesday",
            user_id="evan",
            agent_id="health-agent",
            category="health",
            language="en",
            vector=[0.03, 0.04, 0.05, 0.06, 0.90, 0.12, 0.02, 0.02],
        ),
        MemoryCase(
            key="evan-cycling-negative",
            data="Evan cycles indoors on rainy Sundays",
            text_lemmatized="evan cycle indoors rainy sunday",
            user_id="evan",
            agent_id="health-agent",
            category="health",
            language="en",
            vector=[0.03, 0.04, 0.05, 0.06, 0.89, 0.13, 0.02, 0.02],
        ),
        MemoryCase(
            key="phoenix-launch-budget",
            data="Project Phoenix launch budget requires approval from Mira",
            text_lemmatized="project phoenix launch budget require approval mira",
            user_id="mira",
            agent_id="project-agent",
            category="project",
            language="en",
            vector=[0.04, 0.04, 0.12, 0.04, 0.03, 0.90, 0.08, 0.02],
        ),
        MemoryCase(
            key="phoenix-design-review-negative",
            data="Project Phoenix design review moved to next Tuesday",
            text_lemmatized="project phoenix design review moved next tuesday",
            user_id="mira",
            agent_id="project-agent",
            category="project",
            language="en",
            vector=[0.04, 0.04, 0.12, 0.04, 0.03, 0.91, 0.08, 0.02],
        ),
    ]

    records: list[MemoryCase] = list(base_cases)
    for repeat in range(1, scale):
        for case in base_cases:
            records.append(
                MemoryCase(
                    key=f"{case.key}-distractor-{repeat}",
                    data=f"{case.data} archived distractor {repeat}",
                    text_lemmatized=f"{case.text_lemmatized} archived distractor {repeat}",
                    user_id=case.user_id,
                    agent_id=case.agent_id,
                    category=case.category,
                    language=case.language,
                    vector=_offset(case.vector, repeat * 0.001),
                )
            )
    return records


def build_complex_queries(records: list[MemoryCase]) -> list[QueryCase]:
    by_key = {record.key: record for record in records}
    targets = [
        (
            "hard_window_vs_aisle",
            "Alice flight seat preference",
            "window seat morning flight",
            "alice-window-seat",
            by_key["alice-aisle-seat-negative"].vector,
            {"user_id": "alice"},
        ),
        (
            "cross_tenant_window",
            "Bob flight seat preference",
            "window seat morning flight",
            "bob-window-cross-tenant",
            by_key["alice-window-seat"].vector,
            {"user_id": "bob"},
        ),
        (
            "mixed_priority_boarding",
            "flight upgrade boarding preference",
            "priority boarding upgrade",
            "xiaoli-priority-boarding",
            by_key["xiaoli-priority-boarding"].vector,
            {"user_id": "xiaoli"},
        ),
        (
            "zh_latte_vs_matcha",
            "早晨饮品偏好",
            "拿铁 咖啡 latte coffee",
            "xiaowang-latte",
            by_key["xiaowang-matcha-negative"].vector,
            {"user_id": "xiaowang"},
        ),
        (
            "support_2fa_vs_password",
            "finance portal login help",
            "2fa authenticator two factor",
            "dana-2fa-reset",
            by_key["dana-password-reset-negative"].vector,
            {"user_id": "dana"},
        ),
        (
            "finance_invoice_vs_reimbursement",
            "quarterly finance approval",
            "invoice approval quarterly",
            "carol-invoice-approval",
            by_key["carol-reimbursement-negative"].vector,
            {"user_id": "carol"},
        ),
        (
            "health_running_vs_cycling",
            "weekly exercise habit",
            "five kilometer wednesday",
            "evan-running-wednesday",
            by_key["evan-cycling-negative"].vector,
            {"user_id": "evan"},
        ),
        (
            "project_budget_vs_design",
            "phoenix project approval",
            "launch budget approval mira",
            "phoenix-launch-budget",
            by_key["phoenix-design-review-negative"].vector,
            {"user_id": "mira"},
        ),
    ]
    return [
        QueryCase(
            name=name,
            text=text,
            keyword_query=keyword,
            expected_key=key,
            expected_id=by_key[key].id,
            vector=vector,
            filters=filters,
        )
        for name, text, keyword, key, vector, filters in targets
    ]


def build_workload(scenario: str, scale: int) -> tuple[list[MemoryCase], list[QueryCase]]:
    if scenario == "simple":
        records = build_simple_dataset(scale)
        return records, build_simple_queries(records)
    records = build_complex_dataset(scale)
    return records, build_complex_queries(records)


def percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, int(round((len(ordered) - 1) * pct)))
    return ordered[index]


def ids(results: Any) -> list[str]:
    if results is None:
        return []
    return [str(item.id) for item in results]


def reciprocal_rank(result_ids: list[str], expected_id: str) -> float:
    for index, result_id in enumerate(result_ids, start=1):
        if result_id == expected_id:
            return 1.0 / index
    return 0.0


def summarize_query_results(rows: list[dict[str, Any]]) -> dict[str, Any]:
    latencies = [row["latency_ms"] for row in rows]
    return {
        "queries": len(rows),
        "hit_at_1": sum(1 for row in rows if row["rank"] == 1),
        "hit_at_3": sum(1 for row in rows if row["rank"] is not None and 0 < row["rank"] <= 3),
        "mrr": round(statistics.mean(row["rr"] for row in rows), 4) if rows else 0.0,
        "p50_ms": round(statistics.median(latencies), 2) if latencies else 0.0,
        "p95_ms": round(percentile(latencies, 0.95), 2),
        "details": rows,
    }


def fused_result_ids(semantic_ids: list[str], keyword_ids: list[str]) -> list[str]:
    scores: dict[str, float] = {}
    first_seen: dict[str, int] = {}
    counter = 0
    for result_ids in (semantic_ids, keyword_ids):
        for rank, result_id in enumerate(result_ids, start=1):
            scores[result_id] = scores.get(result_id, 0.0) + 1.0 / (60 + rank)
            if result_id not in first_seen:
                first_seen[result_id] = counter
                counter += 1
    return sorted(scores, key=lambda item: (-scores[item], first_seen[item]))


def rank_of(result_ids: list[str], expected_id: str) -> int | None:
    try:
        return result_ids.index(expected_id) + 1
    except ValueError:
        return None


def timed_call(fn):
    start = time.perf_counter()
    value = fn()
    return value, (time.perf_counter() - start) * 1000


def evaluate_provider(
    name: str,
    store: VectorStoreBase,
    records: list[MemoryCase],
    queries: list[QueryCase],
    top_k: int,
) -> dict[str, Any]:
    vectors = [record.vector for record in records]
    payloads = [record.payload for record in records]
    record_ids = [record.id for record in records]
    key_by_id = {record.id: record.key for record in records}

    _, insert_ms = timed_call(lambda: store.insert(vectors=vectors, payloads=payloads, ids=record_ids))

    semantic_rows = []
    for query in queries:
        results, latency_ms = timed_call(lambda q=query: store.search(q.text, q.vector, top_k=top_k, filters=q.filters))
        result_ids = ids(results)
        rank = rank_of(result_ids, query.expected_id)
        semantic_rows.append(
            {
                "name": query.name,
                "expected_key": query.expected_key,
                "expected_id": query.expected_id,
                "rank": rank,
                "rr": reciprocal_rank(result_ids, query.expected_id),
                "top_keys": [key_by_id.get(result_id, result_id) for result_id in result_ids[:top_k]],
                "top_ids": result_ids[:top_k],
                "latency_ms": round(latency_ms, 2),
            }
        )

    keyword_rows = []
    fused_rows = []
    keyword_supported = True
    for query in queries:
        keyword_results, latency_ms = timed_call(
            lambda q=query: store.keyword_search(q.keyword_query, top_k=top_k, filters=q.filters)
        )
        if keyword_results is None:
            keyword_supported = False
        result_ids = ids(keyword_results)
        rank = rank_of(result_ids, query.expected_id)
        keyword_rows.append(
            {
                "name": query.name,
                "expected_key": query.expected_key,
                "expected_id": query.expected_id,
                "rank": rank,
                "rr": reciprocal_rank(result_ids, query.expected_id),
                "top_keys": [key_by_id.get(result_id, result_id) for result_id in result_ids[:top_k]],
                "top_ids": result_ids[:top_k],
                "latency_ms": round(latency_ms, 2),
            }
        )
        semantic_ids = next(row["top_ids"] for row in semantic_rows if row["name"] == query.name)
        fused_ids = fused_result_ids(semantic_ids, result_ids)[:top_k]
        fused_rank = rank_of(fused_ids, query.expected_id)
        fused_rows.append(
            {
                "name": query.name,
                "expected_key": query.expected_key,
                "expected_id": query.expected_id,
                "rank": fused_rank,
                "rr": reciprocal_rank(fused_ids, query.expected_id),
                "top_keys": [key_by_id.get(result_id, result_id) for result_id in fused_ids],
                "top_ids": fused_ids,
                "latency_ms": 0.0,
            }
        )

    batch_filters = {"run_id": RUN_ID}
    batch_results, batch_ms = timed_call(
        lambda: store.search_batch(
            [query.text for query in queries],
            [query.vector for query in queries],
            top_k=top_k,
            filters=batch_filters,
        )
    )
    batch_rows = []
    for query, results in zip(queries, batch_results):
        result_ids = ids(results)
        rank = rank_of(result_ids, query.expected_id)
        batch_rows.append(
            {
                "name": query.name,
                "expected_key": query.expected_key,
                "expected_id": query.expected_id,
                "rank": rank,
                "rr": reciprocal_rank(result_ids, query.expected_id),
                "top_keys": [key_by_id.get(result_id, result_id) for result_id in result_ids[:top_k]],
                "top_ids": result_ids[:top_k],
            }
        )

    scope_guard_enforced = False
    try:
        store.search("unscoped probe", queries[0].vector, top_k=1, filters=None)
    except Exception:
        scope_guard_enforced = True

    return {
        "provider": name,
        "records": len(records),
        "insert_ms": round(insert_ms, 2),
        "semantic": summarize_query_results(semantic_rows),
        "keyword_supported": keyword_supported,
        "keyword": summarize_query_results(keyword_rows),
        "fused": summarize_query_results(fused_rows),
        "batch": {
            "queries": len(batch_rows),
            "hit_at_1": sum(1 for row in batch_rows if row["rank"] == 1),
            "mrr": round(statistics.mean(row["rr"] for row in batch_rows), 4) if batch_rows else 0.0,
            "total_ms": round(batch_ms, 2),
            "details": batch_rows,
        },
        "scope_guard_enforced": scope_guard_enforced,
    }


def make_gaussdb(collection_name: str) -> GaussDB:
    return GaussDB(
        host=_require_env("GAUSSDB_HOST", "GAUSSDB_TEST_HOST"),
        port=int(_require_env("GAUSSDB_PORT", "GAUSSDB_TEST_PORT")),
        database=_require_env("GAUSSDB_DATABASE", "GAUSSDB_TEST_DATABASE"),
        user=_require_env("GAUSSDB_USER", "GAUSSDB_TEST_USER"),
        password=_require_env("GAUSSDB_PASSWORD", "GAUSSDB_TEST_PASSWORD"),
        collection_name=collection_name,
        embedding_model_dims=DIMENSIONS,
        profile=_env("GAUSSDB_EVAL_PROFILE", default="commercial"),
        metadata_mode=_env("GAUSSDB_EVAL_METADATA_MODE", default="auto"),
        bm25_mode=_env("GAUSSDB_EVAL_BM25_MODE", default="auto"),
        deployment_mode=_env("GAUSSDB_EVAL_DEPLOYMENT_MODE", default="centralized"),
        distribution_mode=_env("GAUSSDB_EVAL_DISTRIBUTION_MODE", default="auto"),
        vector_index_type=_env("GAUSSDB_EVAL_VECTOR_INDEX", default="gsdiskann"),
        vector_metric="cosine",
        require_scoped_filters=True,
        auto_create=True,
    )


def make_pgvector(collection_name: str) -> PGVector:
    return PGVector(
        host=_env("PGVECTOR_HOST", default="127.0.0.1"),
        port=int(_env("PGVECTOR_PORT", default="15432")),
        dbname=_env("PGVECTOR_DATABASE", "PGVECTOR_DBNAME", default="mem0_eval"),
        user=_env("PGVECTOR_USER", default="mem0"),
        password=_env("PGVECTOR_PASSWORD", default="mem0pass"),
        collection_name=collection_name,
        embedding_model_dims=DIMENSIONS,
        diskann=False,
        hnsw=True,
    )


def cleanup(store: VectorStoreBase) -> None:
    try:
        store.delete_col()
    except Exception as exc:
        print(f"cleanup failed for {store.__class__.__name__}: {exc}")


def print_comparison(results: list[dict[str, Any]]) -> None:
    print("\n# mem0 provider comparison")
    print(
        "\n| Provider | Records | Insert ms | Semantic H@1 | Semantic MRR | Keyword | Keyword H@1 | Keyword MRR | Fused H@1 | Fused MRR | Semantic P95 ms | Keyword P95 ms | Batch ms | Scope guard |"
    )
    print("|---|---:|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---|")
    for result in results:
        print(
            "| {provider} | {records} | {insert_ms} | {semantic_h1} | {semantic_mrr} | "
            "{keyword_supported} | {keyword_h1} | {keyword_mrr} | {fused_h1} | {fused_mrr} | "
            "{semantic_p95} | {keyword_p95} | {batch_ms} | {scope_guard} |".format(
                provider=result["provider"],
                records=result["records"],
                insert_ms=result["insert_ms"],
                semantic_h1=result["semantic"]["hit_at_1"],
                semantic_mrr=result["semantic"]["mrr"],
                keyword_supported="yes" if result["keyword_supported"] else "no",
                keyword_h1=result["keyword"]["hit_at_1"],
                keyword_mrr=result["keyword"]["mrr"],
                fused_h1=result["fused"]["hit_at_1"],
                fused_mrr=result["fused"]["mrr"],
                semantic_p95=result["semantic"]["p95_ms"],
                keyword_p95=result["keyword"]["p95_ms"],
                batch_ms=result["batch"]["total_ms"],
                scope_guard="yes" if result["scope_guard_enforced"] else "no",
            )
        )


def print_query_details(results: list[dict[str, Any]]) -> None:
    for result in results:
        print(f"\n## {result['provider']} query details")
        print("| Query | Expected | Semantic rank/top | Keyword rank/top | Fused rank/top |")
        print("|---|---|---|---|---|")
        keyword_by_name = {row["name"]: row for row in result["keyword"]["details"]}
        fused_by_name = {row["name"]: row for row in result["fused"]["details"]}
        for semantic_row in result["semantic"]["details"]:
            keyword_row = keyword_by_name[semantic_row["name"]]
            fused_row = fused_by_name[semantic_row["name"]]
            print(
                "| {query} | {expected} | {semantic_rank}: {semantic_top} | "
                "{keyword_rank}: {keyword_top} | {fused_rank}: {fused_top} |".format(
                    query=semantic_row["name"],
                    expected=semantic_row["expected_key"],
                    semantic_rank=semantic_row["rank"],
                    semantic_top=", ".join(semantic_row["top_keys"]),
                    keyword_rank=keyword_row["rank"],
                    keyword_top=", ".join(keyword_row["top_keys"]),
                    fused_rank=fused_row["rank"],
                    fused_top=", ".join(fused_row["top_keys"]),
                )
            )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", choices=["both", "gaussdb", "pgvector"], default="both")
    parser.add_argument("--scenario", choices=["simple", "complex"], default="complex")
    parser.add_argument("--scale", type=int, default=4, help="Repeat the scenario base cases N times")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--collection-prefix", default="mem0_ab_eval")
    parser.add_argument("--keep", action="store_true", help="Keep benchmark collections for inspection")
    parser.add_argument("--details", action="store_true", help="Print per-query expected/top-key details")
    parser.add_argument("--json", action="store_true", help="Print full JSON result")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    suffix = uuid.uuid4().hex[:8]
    records, queries = build_workload(args.scenario, scale=args.scale)

    providers: list[tuple[str, VectorStoreBase]] = []
    if args.provider in {"both", "gaussdb"}:
        providers.append(("gaussdb", make_gaussdb(f"{args.collection_prefix}_g_{suffix}")))
    if args.provider in {"both", "pgvector"}:
        providers.append(("pgvector", make_pgvector(f"{args.collection_prefix}_p_{suffix}")))

    results: list[dict[str, Any]] = []
    try:
        for name, store in providers:
            print(f"Running {name} with {len(records)} records...")
            results.append(evaluate_provider(name, store, records, queries, top_k=args.top_k))

        print_comparison(results)
        if args.details:
            print_query_details(results)
        if args.json:
            print("\n# full json")
            print(json.dumps(results, ensure_ascii=False, indent=2))
    finally:
        if not args.keep:
            for _, store in providers:
                cleanup(store)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
