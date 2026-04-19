from __future__ import annotations

import argparse
import json
import time
from collections.abc import Callable
from uuid import uuid4

import httpx


def _wait_for_jobs(
    client,
    *,
    job_drainer: Callable[[], int] | None,
    poll_seconds: float,
    max_wait_seconds: float,
) -> dict[str, object]:
    deadline = time.time() + max_wait_seconds
    stats_payload: dict[str, object] = {}
    while True:
        if job_drainer is not None:
            job_drainer()
        stats_response = client.get("/v1/observability/stats")
        stats_response.raise_for_status()
        stats_payload = stats_response.json()
        pending = stats_payload["jobs"]["by_status"].get("pending", 0)
        if pending == 0 or time.time() >= deadline:
            return stats_payload
        time.sleep(poll_seconds)


def _run_scenario(
    client,
    *,
    namespace_name: str,
    agent_name: str,
    external_ref: str,
    event_payload: dict[str, object],
    recall_query: str,
    expected_snippets: list[str],
    job_drainer: Callable[[], int] | None,
    poll_seconds: float,
    max_wait_seconds: float,
) -> dict[str, object]:
    bootstrap = client.post(
        "/v1/adapters/openclaw/bootstrap",
        json={
            "namespace_name": namespace_name,
            "agent_name": agent_name,
            "external_ref": external_ref,
        },
    )
    bootstrap.raise_for_status()
    scope = bootstrap.json()

    event_response = client.post(
        "/v1/adapters/openclaw/events",
        json={
            "namespace_id": scope["namespace_id"],
            "agent_id": scope["agent_id"],
            **event_payload,
        },
    )
    event_response.raise_for_status()

    stats_payload = _wait_for_jobs(
        client,
        job_drainer=job_drainer,
        poll_seconds=poll_seconds,
        max_wait_seconds=max_wait_seconds,
    )

    recall_response = client.post(
        "/v1/adapters/openclaw/recall",
        json={
            "namespace_id": scope["namespace_id"],
            "agent_id": scope["agent_id"],
            "session_id": f"{external_ref}:recall",
            "query": recall_query,
            "context_budget_tokens": 1000,
        },
    )
    recall_response.raise_for_status()
    recall_payload = recall_response.json()
    flattened = "\n".join(
        item for items in recall_payload["brief"].values() for item in items
    )
    missing = [snippet for snippet in expected_snippets if snippet not in flattened]
    passed = not missing

    return {
        "namespace_id": scope["namespace_id"],
        "agent_id": scope["agent_id"],
        "passed": passed,
        "missing": missing,
        "selected_count": recall_payload["trace"]["selected_count"],
        "selected_space_types": recall_payload["trace"]["selected_space_types"],
        "jobs_by_status": stats_payload["jobs"]["by_status"],
        "brief": recall_payload["brief"],
    }


def run_continuity_benchmark(
    client,
    *,
    namespace_suffix: str | None = None,
    job_drainer: Callable[[], int] | None = None,
    poll_seconds: float = 0.5,
    max_wait_seconds: float = 10.0,
) -> dict[str, object]:
    suffix = namespace_suffix or str(uuid4())
    scenarios = [
        {
            "id": "durable-architecture",
            "namespace_name": f"benchmark:{suffix}:architecture",
            "agent_name": "architect",
            "external_ref": f"{suffix}:architecture",
            "event_payload": {
                "session_id": f"{suffix}:session-a",
                "event_type": "architecture_decision",
                "space_hint": "project-space",
                "messages": [
                    {
                        "role": "assistant",
                        "content": "We decided to keep the memory runtime Python-first for v1 and use Postgres, Redis, and pgvector as the baseline stack.",
                    }
                ],
            },
            "recall_query": "What architecture choices were already made for the memory runtime?",
            "expected_snippets": ["Python-first", "Postgres, Redis, and pgvector"],
        },
        {
            "id": "standing-procedure",
            "namespace_name": f"benchmark:{suffix}:procedure",
            "agent_name": "planner",
            "external_ref": f"{suffix}:procedure",
            "event_payload": {
                "session_id": f"{suffix}:session-b",
                "event_type": "policy_update",
                "space_hint": "agent-core",
                "messages": [
                    {
                        "role": "assistant",
                        "content": "Always start architecture responses with a concise summary before implementation details.",
                    }
                ],
            },
            "recall_query": "How should the agent present architecture updates?",
            "expected_snippets": ["concise summary before implementation details"],
        },
        {
            "id": "integration-context",
            "namespace_name": f"benchmark:{suffix}:integration",
            "agent_name": "integrator",
            "external_ref": f"{suffix}:integration",
            "event_payload": {
                "session_id": f"{suffix}:session-c",
                "event_type": "conversation_turn",
                "space_hint": "project-space",
                "messages": [
                    {
                        "role": "assistant",
                        "content": "The runtime exposes adapter APIs for OpenClaw and BunkerAI.",
                    }
                ],
            },
            "recall_query": "Which integration surfaces already exist for the runtime?",
            "expected_snippets": ["OpenClaw and BunkerAI"],
        },
    ]

    results: list[dict[str, object]] = []
    passed = 0
    total_selected = 0
    for scenario in scenarios:
        result = _run_scenario(
            client,
            namespace_name=scenario["namespace_name"],
            agent_name=scenario["agent_name"],
            external_ref=scenario["external_ref"],
            event_payload=scenario["event_payload"],
            recall_query=scenario["recall_query"],
            expected_snippets=scenario["expected_snippets"],
            job_drainer=job_drainer,
            poll_seconds=poll_seconds,
            max_wait_seconds=max_wait_seconds,
        )
        result["id"] = scenario["id"]
        results.append(result)
        total_selected += int(result["selected_count"])
        if result["passed"]:
            passed += 1

    total = len(results)
    return {
        "total": total,
        "passed": passed,
        "failed": total - passed,
        "pass_rate": round((passed / total) if total else 1.0, 4),
        "metrics": {
            "avg_selected_count": round((total_selected / total) if total else 0.0, 4),
        },
        "results": results,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run continuity benchmark scenarios.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8080")
    parser.add_argument("--namespace-suffix", default=None)
    parser.add_argument("--poll-seconds", type=float, default=0.5)
    parser.add_argument("--max-wait-seconds", type=float, default=10.0)
    args = parser.parse_args(argv)

    with httpx.Client(base_url=args.base_url, timeout=10.0) as client:
        report = run_continuity_benchmark(
            client,
            namespace_suffix=args.namespace_suffix,
            poll_seconds=args.poll_seconds,
            max_wait_seconds=args.max_wait_seconds,
        )

    print(json.dumps(report, ensure_ascii=False))
    return 0 if report["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
