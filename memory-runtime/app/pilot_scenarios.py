from __future__ import annotations

import argparse
import json
import time
from collections.abc import Callable
from uuid import uuid4

import httpx

from app.pilot_artifacts import default_artifact_run_name, export_trace_bundle


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


def _bootstrap_scope(client, *, namespace_name: str, agent_name: str, external_ref: str) -> dict[str, str]:
    response = client.post(
        "/v1/adapters/openclaw/bootstrap",
        json={
            "namespace_name": namespace_name,
            "agent_name": agent_name,
            "external_ref": external_ref,
        },
    )
    response.raise_for_status()
    return response.json()


def _create_event(
    client,
    *,
    namespace_id: str,
    agent_id: str,
    event_type: str,
    content: str,
    session_id: str | None = None,
    space_hint: str | None = None,
    role: str = "assistant",
) -> None:
    response = client.post(
        "/v1/adapters/openclaw/events",
        json={
            "namespace_id": namespace_id,
            "agent_id": agent_id,
            "session_id": session_id,
            "event_type": event_type,
            "space_hint": space_hint,
            "messages": [{"role": role, "content": content}],
        },
    )
    response.raise_for_status()


def _flatten_brief(brief: dict[str, list[str]]) -> str:
    return "\n".join(item for items in brief.values() for item in items)


def _run_recall(
    client,
    *,
    namespace_id: str,
    agent_id: str,
    session_id: str,
    query: str,
) -> dict[str, object]:
    response = client.post(
        "/v1/adapters/openclaw/recall",
        json={
            "namespace_id": namespace_id,
            "agent_id": agent_id,
            "session_id": session_id,
            "query": query,
            "context_budget_tokens": 1000,
        },
    )
    response.raise_for_status()
    return response.json()


def _run_durable_architecture_scenario(
    client,
    *,
    suffix: str,
    job_drainer: Callable[[], int] | None,
    poll_seconds: float,
    max_wait_seconds: float,
) -> dict[str, object]:
    scope = _bootstrap_scope(
        client,
        namespace_name=f"pilot-scenarios:{suffix}:architecture",
        agent_name="architect",
        external_ref=f"{suffix}:architecture",
    )
    _create_event(
        client,
        namespace_id=scope["namespace_id"],
        agent_id=scope["agent_id"],
        session_id=f"{suffix}:arch-source",
        event_type="architecture_decision",
        space_hint="project-space",
        content="The memory runtime stays Python-first for v1 and uses Postgres, Redis, and pgvector.",
    )
    stats_payload = _wait_for_jobs(
        client,
        job_drainer=job_drainer,
        poll_seconds=poll_seconds,
        max_wait_seconds=max_wait_seconds,
    )
    recall = _run_recall(
        client,
        namespace_id=scope["namespace_id"],
        agent_id=scope["agent_id"],
        session_id=f"{suffix}:arch-recall",
        query="What architecture decisions already exist for the memory runtime?",
    )
    flattened = _flatten_brief(recall["brief"])
    missing = [
        snippet
        for snippet in ("Python-first", "Postgres, Redis, and pgvector")
        if snippet not in flattened
    ]
    return {
        "id": "durable-architecture-decision",
        "passed": not missing,
        "missing": missing,
        "trace": recall["trace"],
        "jobs_by_status": stats_payload["jobs"]["by_status"],
    }


def _run_standing_procedure_scenario(
    client,
    *,
    suffix: str,
    job_drainer: Callable[[], int] | None,
    poll_seconds: float,
    max_wait_seconds: float,
) -> dict[str, object]:
    scope = _bootstrap_scope(
        client,
        namespace_name=f"pilot-scenarios:{suffix}:procedure",
        agent_name="planner",
        external_ref=f"{suffix}:procedure",
    )
    _create_event(
        client,
        namespace_id=scope["namespace_id"],
        agent_id=scope["agent_id"],
        session_id=f"{suffix}:proc-policy",
        event_type="policy_update",
        space_hint="agent-core",
        content="Always start architecture responses with a concise summary before implementation details.",
    )
    _create_event(
        client,
        namespace_id=scope["namespace_id"],
        agent_id=scope["agent_id"],
        session_id=f"{suffix}:proc-noise",
        event_type="conversation_turn",
        space_hint="project-space",
        content="Project note: finalize Docker health checks and env var names later this week.",
    )
    stats_payload = _wait_for_jobs(
        client,
        job_drainer=job_drainer,
        poll_seconds=poll_seconds,
        max_wait_seconds=max_wait_seconds,
    )
    recall = _run_recall(
        client,
        namespace_id=scope["namespace_id"],
        agent_id=scope["agent_id"],
        session_id=f"{suffix}:proc-recall",
        query="How should the agent present architecture updates?",
    )
    flattened = _flatten_brief(recall["brief"])
    missing = [
        snippet
        for snippet in ("concise summary before implementation details",)
        if snippet not in flattened
    ]
    return {
        "id": "standing-procedure-recall",
        "passed": not missing,
        "missing": missing,
        "trace": recall["trace"],
        "jobs_by_status": stats_payload["jobs"]["by_status"],
    }


def _run_active_session_carryover_scenario(
    client,
    *,
    suffix: str,
    job_drainer: Callable[[], int] | None,
    poll_seconds: float,
    max_wait_seconds: float,
) -> dict[str, object]:
    scope = _bootstrap_scope(
        client,
        namespace_name=f"pilot-scenarios:{suffix}:session",
        agent_name="operator",
        external_ref=f"{suffix}:session",
    )
    _create_event(
        client,
        namespace_id=scope["namespace_id"],
        agent_id=scope["agent_id"],
        session_id=f"{suffix}:carry-project",
        event_type="architecture_decision",
        space_hint="project-space",
        content="The project already uses Redis for background jobs.",
    )
    active_session_id = f"{suffix}:carry-active"
    _create_event(
        client,
        namespace_id=scope["namespace_id"],
        agent_id=scope["agent_id"],
        session_id=active_session_id,
        event_type="conversation_turn",
        space_hint="session-space",
        role="user",
        content="Right now I am preparing the pilot acceptance checklist for OpenClaw.",
    )
    stats_payload = _wait_for_jobs(
        client,
        job_drainer=job_drainer,
        poll_seconds=poll_seconds,
        max_wait_seconds=max_wait_seconds,
    )
    recall = _run_recall(
        client,
        namespace_id=scope["namespace_id"],
        agent_id=scope["agent_id"],
        session_id=active_session_id,
        query="What am I doing in this session right now?",
    )
    flattened = _flatten_brief(recall["brief"])
    missing = [
        snippet
        for snippet in ("pilot acceptance checklist",)
        if snippet not in flattened
    ]
    return {
        "id": "active-session-carryover",
        "passed": not missing,
        "missing": missing,
        "trace": recall["trace"],
        "jobs_by_status": stats_payload["jobs"]["by_status"],
    }


def _run_cross_session_continuity_scenario(
    client,
    *,
    suffix: str,
    job_drainer: Callable[[], int] | None,
    poll_seconds: float,
    max_wait_seconds: float,
) -> dict[str, object]:
    scope = _bootstrap_scope(
        client,
        namespace_name=f"pilot-scenarios:{suffix}:continuity",
        agent_name="continuity",
        external_ref=f"{suffix}:continuity",
    )
    _create_event(
        client,
        namespace_id=scope["namespace_id"],
        agent_id=scope["agent_id"],
        session_id=f"{suffix}:continuity-a",
        event_type="conversation_turn",
        space_hint="project-space",
        content="We stopped after implementing namespaces, recall, consolidation, and lifecycle for the memory runtime.",
    )
    stats_payload = _wait_for_jobs(
        client,
        job_drainer=job_drainer,
        poll_seconds=poll_seconds,
        max_wait_seconds=max_wait_seconds,
    )
    recall = _run_recall(
        client,
        namespace_id=scope["namespace_id"],
        agent_id=scope["agent_id"],
        session_id=f"{suffix}:continuity-b",
        query="Where did we leave off on the memory runtime?",
    )
    flattened = _flatten_brief(recall["brief"])
    missing = [
        snippet
        for snippet in ("namespaces, recall, consolidation, and lifecycle",)
        if snippet not in flattened
    ]
    return {
        "id": "cross-session-continuity",
        "passed": not missing,
        "missing": missing,
        "trace": recall["trace"],
        "jobs_by_status": stats_payload["jobs"]["by_status"],
    }


def _run_noise_resistance_scenario(
    client,
    *,
    suffix: str,
    job_drainer: Callable[[], int] | None,
    poll_seconds: float,
    max_wait_seconds: float,
) -> dict[str, object]:
    scope = _bootstrap_scope(
        client,
        namespace_name=f"pilot-scenarios:{suffix}:noise",
        agent_name="researcher",
        external_ref=f"{suffix}:noise",
    )
    for content in (
        "Temporary scratch note: maybe rename env vars next quarter.",
        "Book flights for the conference next month.",
        "Old deprecated deployment note from a previous prototype.",
    ):
        _create_event(
            client,
            namespace_id=scope["namespace_id"],
            agent_id=scope["agent_id"],
            session_id=f"{suffix}:noise-session",
            event_type="conversation_turn",
            space_hint="session-space",
            content=content,
        )
    _create_event(
        client,
        namespace_id=scope["namespace_id"],
        agent_id=scope["agent_id"],
        session_id=f"{suffix}:noise-project",
        event_type="architecture_decision",
        space_hint="project-space",
        content="The architecture work should prioritize the memory worker and Postgres-backed recall pipeline.",
    )
    stats_payload = _wait_for_jobs(
        client,
        job_drainer=job_drainer,
        poll_seconds=poll_seconds,
        max_wait_seconds=max_wait_seconds,
    )
    recall = _run_recall(
        client,
        namespace_id=scope["namespace_id"],
        agent_id=scope["agent_id"],
        session_id=f"{suffix}:noise-recall",
        query="What matters for the current architecture work?",
    )
    flattened = _flatten_brief(recall["brief"])
    missing = [
        snippet
        for snippet in ("memory worker and Postgres-backed recall pipeline",)
        if snippet not in flattened
    ]
    unexpected = [
        snippet
        for snippet in ("Book flights", "deprecated deployment note")
        if snippet in flattened
    ]
    return {
        "id": "noise-resistance",
        "passed": not missing and not unexpected,
        "missing": missing,
        "unexpected": unexpected,
        "trace": recall["trace"],
        "jobs_by_status": stats_payload["jobs"]["by_status"],
    }


def run_pilot_scenarios(
    client,
    *,
    namespace_suffix: str | None = None,
    artifact_run_name: str | None = None,
    job_drainer: Callable[[], int] | None = None,
    poll_seconds: float = 0.5,
    max_wait_seconds: float = 10.0,
) -> dict[str, object]:
    suffix = namespace_suffix or str(uuid4())
    scenario_runners = [
        _run_durable_architecture_scenario,
        _run_standing_procedure_scenario,
        _run_active_session_carryover_scenario,
        _run_cross_session_continuity_scenario,
        _run_noise_resistance_scenario,
    ]

    results: list[dict[str, object]] = []
    passed = 0
    total_selected = 0
    for runner in scenario_runners:
        result = runner(
            client,
            suffix=suffix,
            job_drainer=job_drainer,
            poll_seconds=poll_seconds,
            max_wait_seconds=max_wait_seconds,
        )
        results.append(result)
        total_selected += int(result["trace"]["selected_count"])
        if result["passed"]:
            passed += 1

    total = len(results)
    artifact_dir = export_trace_bundle(
        category="pilot-scenarios",
        run_name=artifact_run_name or default_artifact_run_name("pilot-scenarios"),
        payloads={str(result["id"]): result for result in results},
    )
    return {
        "total": total,
        "passed": passed,
        "failed": total - passed,
        "artifact_dir": str(artifact_dir),
        "pass_rate": round((passed / total) if total else 1.0, 4),
        "metrics": {
            "avg_selected_count": round((total_selected / total) if total else 0.0, 4),
        },
        "results": results,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the OpenClaw pilot scenario subset.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8080")
    parser.add_argument("--namespace-suffix", default=None)
    parser.add_argument("--artifact-run-name", default=None)
    parser.add_argument("--poll-seconds", type=float, default=0.5)
    parser.add_argument("--max-wait-seconds", type=float, default=10.0)
    args = parser.parse_args(argv)

    with httpx.Client(base_url=args.base_url, timeout=10.0) as client:
        report = run_pilot_scenarios(
            client,
            namespace_suffix=args.namespace_suffix,
            artifact_run_name=args.artifact_run_name,
            poll_seconds=args.poll_seconds,
            max_wait_seconds=args.max_wait_seconds,
        )

    print(json.dumps(report, ensure_ascii=False))
    return 0 if report["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
