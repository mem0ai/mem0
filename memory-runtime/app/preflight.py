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
    baseline_completed: int,
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
        by_status = stats_payload["jobs"]["by_status"]
        completed = by_status.get("completed", 0)
        pending = by_status.get("pending", 0)
        if pending == 0 and completed > baseline_completed:
            return stats_payload
        if time.time() >= deadline:
            return stats_payload
        time.sleep(poll_seconds)


def run_preflight(
    client,
    *,
    namespace_suffix: str | None = None,
    job_drainer: Callable[[], int] | None = None,
    poll_seconds: float = 0.5,
    max_wait_seconds: float = 10.0,
) -> dict[str, object]:
    suffix = namespace_suffix or str(uuid4())

    health_response = client.get("/healthz")
    health_response.raise_for_status()

    metrics_response = client.get("/metrics")
    metrics_response.raise_for_status()

    baseline_stats_response = client.get("/v1/observability/stats")
    baseline_stats_response.raise_for_status()
    baseline_stats = baseline_stats_response.json()
    baseline_completed = baseline_stats["jobs"]["by_status"].get("completed", 0)

    bootstrap_response = client.post(
        "/v1/adapters/openclaw/bootstrap",
        json={
            "namespace_name": f"preflight:{suffix}",
            "agent_name": "preflight-agent",
            "external_ref": f"preflight:{suffix}",
        },
    )
    bootstrap_response.raise_for_status()
    scope = bootstrap_response.json()

    event_response = client.post(
        "/v1/adapters/openclaw/events",
        json={
            "namespace_id": scope["namespace_id"],
            "agent_id": scope["agent_id"],
            "session_id": f"{suffix}:preflight-session",
            "event_type": "architecture_decision",
            "space_hint": "project-space",
            "messages": [
                {
                    "role": "assistant",
                    "content": "Preflight check confirmed the runtime should use a dedicated memory worker and Postgres-backed recall.",
                }
            ],
        },
    )
    event_response.raise_for_status()

    final_stats = _wait_for_jobs(
        client,
        baseline_completed=baseline_completed,
        job_drainer=job_drainer,
        poll_seconds=poll_seconds,
        max_wait_seconds=max_wait_seconds,
    )

    recall_response = client.post(
        "/v1/adapters/openclaw/recall",
        json={
            "namespace_id": scope["namespace_id"],
            "agent_id": scope["agent_id"],
            "session_id": f"{suffix}:preflight-recall",
            "query": "What setup did the preflight check confirm for the memory runtime?",
            "context_budget_tokens": 1000,
        },
    )
    recall_response.raise_for_status()
    recall_payload = recall_response.json()
    flattened = "\n".join(
        item for items in recall_payload["brief"].values() for item in items
    )

    checks = {
        "healthz_ok": health_response.json().get("status") == "ok",
        "metrics_exposed": "jobs_processed_total" in metrics_response.text,
        "observability_available": isinstance(final_stats.get("jobs"), dict),
        "worker_processed_job": final_stats["jobs"]["by_status"].get("completed", 0) > baseline_completed,
        "recall_round_trip": "dedicated memory worker and Postgres-backed recall" in flattened,
    }
    passed = all(checks.values())

    return {
        "status": "pass" if passed else "fail",
        "checks": checks,
        "namespace_id": scope["namespace_id"],
        "agent_id": scope["agent_id"],
        "jobs_by_status": final_stats["jobs"]["by_status"],
        "selected_count": recall_payload["trace"]["selected_count"],
        "selected_space_types": recall_payload["trace"]["selected_space_types"],
        "brief": recall_payload["brief"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run a preflight check for the memory runtime.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8080")
    parser.add_argument("--namespace-suffix", default=None)
    parser.add_argument("--poll-seconds", type=float, default=0.5)
    parser.add_argument("--max-wait-seconds", type=float, default=10.0)
    args = parser.parse_args(argv)

    with httpx.Client(base_url=args.base_url, timeout=10.0) as client:
        report = run_preflight(
            client,
            namespace_suffix=args.namespace_suffix,
            poll_seconds=args.poll_seconds,
            max_wait_seconds=args.max_wait_seconds,
        )

    print(json.dumps(report, ensure_ascii=False))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
