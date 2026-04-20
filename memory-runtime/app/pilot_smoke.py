from __future__ import annotations

import argparse
import json
import time
from collections.abc import Callable
from uuid import uuid4

import httpx

from app.pilot_artifacts import default_artifact_run_name, export_trace_bundle


def run_pilot_smoke(
    client,
    *,
    namespace_suffix: str | None = None,
    artifact_run_name: str | None = None,
    poll_seconds: float = 0.5,
    max_wait_seconds: float = 10.0,
    job_drainer: Callable[[], int] | None = None,
) -> dict[str, object]:
    suffix = namespace_suffix or str(uuid4())
    namespace_name = f"pilot:{suffix}"
    external_ref = f"pilot-user:{suffix}"

    bootstrap = client.post(
        "/v1/adapters/openclaw/bootstrap",
        json={
            "namespace_name": namespace_name,
            "agent_name": "primary",
            "external_ref": external_ref,
        },
    )
    bootstrap.raise_for_status()
    scope = bootstrap.json()
    namespace_id = scope["namespace_id"]
    agent_id = scope["agent_id"]

    durable = client.post(
        "/v1/adapters/openclaw/events",
        json={
            "namespace_id": namespace_id,
            "agent_id": agent_id,
            "event_type": "architecture_decision",
            "space_hint": "project-space",
            "messages": [
                {
                    "role": "assistant",
                    "content": "The OpenClaw pilot should use memory-runtime with Postgres, Redis, and a dedicated memory worker.",
                }
            ],
        },
    )
    durable.raise_for_status()

    session_event = client.post(
        "/v1/adapters/openclaw/events",
        json={
            "namespace_id": namespace_id,
            "agent_id": agent_id,
            "session_id": "run_pilot_smoke_session",
            "event_type": "conversation_turn",
            "space_hint": "session-space",
            "messages": [
                {
                    "role": "user",
                    "content": "Next I need a runbook and acceptance checklist for the OpenClaw MVP pilot.",
                }
            ],
        },
    )
    session_event.raise_for_status()

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
            break
        time.sleep(poll_seconds)

    recall = client.post(
        "/v1/adapters/openclaw/recall",
        json={
            "namespace_id": namespace_id,
            "agent_id": agent_id,
            "session_id": "run_pilot_smoke_recall",
            "query": "What stack and operational setup were chosen for the OpenClaw pilot?",
            "context_budget_tokens": 1000,
        },
    )
    recall.raise_for_status()

    search = client.post(
        "/v1/adapters/openclaw/search",
        json={
            "namespace_id": namespace_id,
            "agent_id": agent_id,
            "session_id": "run_pilot_smoke_session",
            "query": "runbook acceptance checklist",
            "limit": 5,
        },
    )
    search.raise_for_status()

    listing = client.get(
        "/v1/adapters/openclaw/memories",
        params={"namespace_id": namespace_id, "agent_id": agent_id},
    )
    listing.raise_for_status()

    recall_payload = recall.json()
    search_payload = search.json()
    listing_payload = listing.json()
    artifact_dir = export_trace_bundle(
        category="pilot-smoke",
        run_name=artifact_run_name or default_artifact_run_name("pilot-smoke"),
        payloads={
            "bootstrap_scope": scope,
            "recall_payload": recall_payload,
            "search_payload": search_payload,
            "list_payload": listing_payload,
            "observability_stats": stats_payload,
        },
    )

    return {
        "namespace_id": namespace_id,
        "agent_id": agent_id,
        "artifact_dir": str(artifact_dir),
        "durable_event_id": durable.json()["event"]["id"],
        "session_event_id": session_event.json()["event"]["id"],
        "recall_prior_decisions": recall_payload["brief"]["prior_decisions"],
        "recall_active_project_context": recall_payload["brief"]["active_project_context"],
        "session_search_results": [item["memory"] for item in search_payload["results"]],
        "long_term_list_results": [item["memory"] for item in listing_payload["results"][:5]],
        "jobs_by_status": stats_payload["jobs"]["by_status"],
        "metrics": stats_payload["metrics"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the OpenClaw pilot smoke scenario.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8080")
    parser.add_argument("--namespace-suffix", default=None)
    parser.add_argument("--artifact-run-name", default=None)
    parser.add_argument("--poll-seconds", type=float, default=0.5)
    parser.add_argument("--max-wait-seconds", type=float, default=10.0)
    args = parser.parse_args(argv)

    with httpx.Client(base_url=args.base_url, timeout=10.0) as client:
        report = run_pilot_smoke(
            client,
            namespace_suffix=args.namespace_suffix,
            artifact_run_name=args.artifact_run_name,
            poll_seconds=args.poll_seconds,
            max_wait_seconds=args.max_wait_seconds,
        )

    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
