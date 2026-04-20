from __future__ import annotations

import argparse
import json
from typing import Any

import httpx
from sqlalchemy import Select, desc, select

from app.database import get_session_factory
from app.models.memory_unit import MemoryUnit


def fetch_memory_units(
    *,
    namespace_id: str | None = None,
    agent_id: str | None = None,
    statuses: list[str] | None = None,
    limit: int = 10,
) -> list[MemoryUnit]:
    stmt: Select[tuple[MemoryUnit]] = select(MemoryUnit).order_by(desc(MemoryUnit.created_at)).limit(limit)
    if namespace_id:
        stmt = stmt.where(MemoryUnit.namespace_id == namespace_id)
    if agent_id:
        stmt = stmt.where(MemoryUnit.agent_id == agent_id)
    if statuses:
        stmt = stmt.where(MemoryUnit.status.in_(statuses))

    session_factory = get_session_factory()
    with session_factory() as session:
        return list(session.execute(stmt).scalars())


def memory_units_to_report(units: list[MemoryUnit]) -> list[dict[str, Any]]:
    return [
        {
            "id": unit.id,
            "kind": unit.kind,
            "scope": unit.scope,
            "status": unit.status,
            "summary": unit.summary,
            "content": unit.content,
            "primary_space_id": unit.primary_space_id,
            "supersedes_memory_id": unit.supersedes_memory_id,
            "created_at": unit.created_at.isoformat(),
            "updated_at": unit.updated_at.isoformat(),
        }
        for unit in units
    ]


def explain_recall(
    *,
    base_url: str,
    namespace_id: str,
    agent_id: str,
    session_id: str,
    query: str,
    context_budget_tokens: int,
) -> dict[str, Any]:
    with httpx.Client(base_url=base_url, timeout=15.0) as client:
        response = client.post(
            "/v1/adapters/openclaw/recall",
            json={
                "namespace_id": namespace_id,
                "agent_id": agent_id,
                "session_id": session_id,
                "query": query,
                "context_budget_tokens": context_budget_tokens,
            },
        )
        response.raise_for_status()
        payload = response.json()

    explanations = [
        {
            "episode_id": item["episode_id"],
            "space_type": item["space_type"],
            "slot": item["slot"],
            "decisive_signal": item["decisive_signal"],
            "why": item["why"],
        }
        for item in payload["trace"]["selection_explanations"]
    ]

    return {
        "brief": payload["brief"],
        "trace_summary": {
            "candidate_count": payload["trace"]["candidate_count"],
            "selected_count": payload["trace"]["selected_count"],
            "selected_space_types": payload["trace"]["selected_space_types"],
        },
        "selection_explanations": explanations,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Inspect memory-runtime pilot state.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser("list", help="List recent memory units.")
    list_parser.add_argument("--namespace-id", default=None)
    list_parser.add_argument("--agent-id", default=None)
    list_parser.add_argument("--status", action="append", dest="statuses", default=None)
    list_parser.add_argument("--limit", type=int, default=10)

    lifecycle_parser = subparsers.add_parser(
        "lifecycle",
        help="List archived or superseded memory units.",
    )
    lifecycle_parser.add_argument("--namespace-id", default=None)
    lifecycle_parser.add_argument("--agent-id", default=None)
    lifecycle_parser.add_argument("--limit", type=int, default=10)

    recall_parser = subparsers.add_parser(
        "explain-recall",
        help="Run recall and print selection explanations.",
    )
    recall_parser.add_argument("--base-url", default="http://127.0.0.1:8080")
    recall_parser.add_argument("--namespace-id", required=True)
    recall_parser.add_argument("--agent-id", required=True)
    recall_parser.add_argument("--session-id", required=True)
    recall_parser.add_argument("--query", required=True)
    recall_parser.add_argument("--context-budget-tokens", type=int, default=1000)

    args = parser.parse_args(argv)

    if args.command == "list":
        units = fetch_memory_units(
            namespace_id=args.namespace_id,
            agent_id=args.agent_id,
            statuses=args.statuses,
            limit=args.limit,
        )
        print(json.dumps({"results": memory_units_to_report(units)}, ensure_ascii=False))
        return 0

    if args.command == "lifecycle":
        units = fetch_memory_units(
            namespace_id=args.namespace_id,
            agent_id=args.agent_id,
            statuses=["archived", "superseded"],
            limit=args.limit,
        )
        print(json.dumps({"results": memory_units_to_report(units)}, ensure_ascii=False))
        return 0

    report = explain_recall(
        base_url=args.base_url,
        namespace_id=args.namespace_id,
        agent_id=args.agent_id,
        session_id=args.session_id,
        query=args.query,
        context_budget_tokens=args.context_budget_tokens,
    )
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
