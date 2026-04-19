from __future__ import annotations

import json
import unittest
from pathlib import Path


class RetrievalServiceContractTests(unittest.TestCase):
    def test_default_space_filters_for_isolated_agent(self) -> None:
        from app.services.retrieval import RetrievalService

        spaces = RetrievalService.resolve_space_filters(
            namespace_mode="isolated",
            requested_space_filter=None,
        )

        self.assertEqual(spaces, ["session-space", "project-space", "agent-core"])

    def test_default_space_filters_for_shared_namespace(self) -> None:
        from app.services.retrieval import RetrievalService

        spaces = RetrievalService.resolve_space_filters(
            namespace_mode="shared",
            requested_space_filter=None,
        )

        self.assertEqual(spaces, ["session-space", "project-space", "agent-core", "shared-space"])

    def test_rank_candidates_prefers_query_overlap_and_importance(self) -> None:
        from app.services.retrieval import RetrievalCandidate, RetrievalService

        ranked = RetrievalService.rank_candidates(
            query="architecture decisions for memory runtime",
            candidates=[
                RetrievalCandidate(
                    episode_id="ep-session",
                    space_type="session-space",
                    event_type="conversation_turn",
                    summary="conversation_turn: Continue the implementation work tomorrow",
                    raw_text="user: Continue the implementation work tomorrow",
                    importance_hint="normal",
                    created_at="2026-04-20T10:05:00+00:00",
                    session_id="run_1",
                ),
                RetrievalCandidate(
                    episode_id="ep-decision",
                    space_type="project-space",
                    event_type="architecture_decision",
                    summary="architecture_decision: We chose Python-first architecture for the memory runtime.",
                    raw_text="assistant: We chose Python-first architecture for the memory runtime.",
                    importance_hint="high",
                    created_at="2026-04-20T09:00:00+00:00",
                    session_id="run_0",
                ),
            ],
            active_session_id="run_1",
        )

        self.assertEqual(ranked[0].episode_id, "ep-decision")

    def test_build_memory_brief_matches_golden_fixture(self) -> None:
        from app.services.retrieval import RetrievalCandidate, RetrievalService

        ranked = [
            RetrievalCandidate(
                episode_id="ep-project-context",
                space_type="project-space",
                event_type="conversation_turn",
                summary="conversation_turn: The memory runtime uses Postgres, Redis, and pgvector as the baseline stack.",
                raw_text="assistant: The memory runtime uses Postgres, Redis, and pgvector as the baseline stack.",
                importance_hint="normal",
                created_at="2026-04-20T08:00:00+00:00",
                session_id="run_0",
            ),
            RetrievalCandidate(
                episode_id="ep-decision",
                space_type="project-space",
                event_type="architecture_decision",
                summary="architecture_decision: We decided to keep the memory runtime Python-first for v1 and postpone any Go rewrite.",
                raw_text="assistant: We decided to keep the memory runtime Python-first for v1 and postpone any Go rewrite.",
                importance_hint="high",
                created_at="2026-04-20T09:00:00+00:00",
                session_id="run_0",
            ),
            RetrievalCandidate(
                episode_id="ep-policy",
                space_type="agent-core",
                event_type="policy_update",
                summary="policy_update: Always produce concise architecture summaries before implementation details.",
                raw_text="assistant: Always produce concise architecture summaries before implementation details.",
                importance_hint="high",
                created_at="2026-04-20T09:30:00+00:00",
                session_id="run_0",
            ),
            RetrievalCandidate(
                episode_id="ep-session",
                space_type="session-space",
                event_type="conversation_turn",
                summary="conversation_turn: Continue the Phase D recall MVP work for the memory runtime.",
                raw_text="user: Continue the Phase D recall MVP work for the memory runtime.",
                importance_hint="normal",
                created_at="2026-04-20T10:00:00+00:00",
                session_id="run_123",
            ),
        ]

        brief = RetrievalService.build_memory_brief(ranked)

        fixture_path = (
            Path(__file__).resolve().parents[1] / "fixtures" / "golden" / "recall_brief_expected.json"
        )
        expected = json.loads(fixture_path.read_text())

        self.assertEqual(brief, expected)
