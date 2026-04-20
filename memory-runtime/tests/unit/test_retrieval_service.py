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
                    usefulness_score=0.0,
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
                    usefulness_score=0.0,
                ),
            ],
            active_session_id="run_1",
        )

        self.assertEqual(ranked[0].episode_id, "ep-decision")

    def test_rank_candidates_prefers_positive_usefulness_feedback(self) -> None:
        from app.services.retrieval import RetrievalCandidate, RetrievalService

        ranked = RetrievalService.rank_candidates(
            query="what database stack does the memory runtime use",
            candidates=[
                RetrievalCandidate(
                    episode_id="ep-newer",
                    space_type="project-space",
                    event_type="conversation_turn",
                    summary="conversation_turn: The memory runtime uses SQLite for temporary scratch notes.",
                    raw_text="assistant: The memory runtime uses SQLite for temporary scratch notes.",
                    importance_hint="normal",
                    created_at="2026-04-20T10:10:00+00:00",
                    session_id="run_2",
                    usefulness_score=0.0,
                ),
                RetrievalCandidate(
                    episode_id="ep-helpful",
                    space_type="project-space",
                    event_type="conversation_turn",
                    summary="conversation_turn: The memory runtime uses Postgres and Redis as the core stack.",
                    raw_text="assistant: The memory runtime uses Postgres and Redis as the core stack.",
                    importance_hint="normal",
                    created_at="2026-04-20T09:00:00+00:00",
                    session_id="run_1",
                    usefulness_score=1.0,
                ),
            ],
            active_session_id=None,
        )

        self.assertEqual(ranked[0].episode_id, "ep-helpful")

    def test_rank_candidates_prefers_agent_core_for_procedural_queries(self) -> None:
        from app.services.retrieval import RetrievalCandidate, RetrievalService

        ranked = RetrievalService.rank_candidates(
            query="How should the agent present architecture updates?",
            candidates=[
                RetrievalCandidate(
                    episode_id="ep-project-note",
                    space_type="project-space",
                    event_type="conversation_turn",
                    summary="conversation_turn: This is only a temporary scratch note and should not dominate recall.",
                    raw_text="assistant: This is only a temporary scratch note and should not dominate recall.",
                    importance_hint="normal",
                    created_at="2026-04-20T10:10:00+00:00",
                    session_id="run_2",
                    usefulness_score=0.0,
                ),
                RetrievalCandidate(
                    episode_id="ep-policy",
                    space_type="agent-core",
                    event_type="policy_update",
                    summary="policy_update: Always produce concise architecture summaries before implementation details.",
                    raw_text="assistant: Always produce concise architecture summaries before implementation details.",
                    importance_hint="high",
                    created_at="2026-04-20T09:00:00+00:00",
                    session_id="run_1",
                    usefulness_score=0.0,
                ),
            ],
            active_session_id="run_2",
        )

        self.assertEqual(ranked[0].episode_id, "ep-policy")

    def test_select_candidates_for_brief_skips_low_signal_project_noise(self) -> None:
        from app.services.retrieval import RetrievalCandidate, RetrievalService

        ranked = RetrievalService.rank_candidates(
            query="How should the agent present architecture updates?",
            candidates=[
                RetrievalCandidate(
                    episode_id="ep-policy",
                    space_type="agent-core",
                    event_type="policy_update",
                    summary="policy_update: Always produce concise architecture summaries before implementation details.",
                    raw_text="assistant: Always produce concise architecture summaries before implementation details.",
                    importance_hint="high",
                    created_at="2026-04-20T09:00:00+00:00",
                    session_id="run_1",
                    usefulness_score=0.0,
                ),
                RetrievalCandidate(
                    episode_id="ep-runtime",
                    space_type="project-space",
                    event_type="conversation_turn",
                    summary="conversation_turn: The memory runtime uses Postgres, Redis, and pgvector as the baseline stack.",
                    raw_text="assistant: The memory runtime uses Postgres, Redis, and pgvector as the baseline stack.",
                    importance_hint="normal",
                    created_at="2026-04-20T09:05:00+00:00",
                    session_id="run_1",
                    usefulness_score=0.0,
                ),
                RetrievalCandidate(
                    episode_id="ep-noise",
                    space_type="project-space",
                    event_type="conversation_turn",
                    summary="conversation_turn: This is only a temporary scratch note and should not dominate recall.",
                    raw_text="assistant: This is only a temporary scratch note and should not dominate recall.",
                    importance_hint="normal",
                    created_at="2026-04-20T10:10:00+00:00",
                    session_id="run_3",
                    usefulness_score=0.0,
                ),
            ],
            active_session_id="run_2",
        )

        selected = RetrievalService.select_candidates_for_brief(
            query="How should the agent present architecture updates?",
            ranked_candidates=ranked,
            active_session_id="run_2",
            context_budget_tokens=800,
        )

        self.assertEqual([candidate.episode_id for candidate in selected], ["ep-policy", "ep-runtime"])

    def test_rank_candidates_prefers_durable_project_context_over_active_session_scratch(self) -> None:
        from app.services.retrieval import RetrievalCandidate, RetrievalService

        ranked = RetrievalService.rank_candidates(
            query="What durable project context should I keep in mind for the memory runtime?",
            candidates=[
                RetrievalCandidate(
                    episode_id="ep-session-scratch",
                    space_type="session-space",
                    event_type="conversation_turn",
                    summary="conversation_turn: Temporary naming experiment: maybe rename the runtime endpoint later.",
                    raw_text="assistant: Temporary naming experiment: maybe rename the runtime endpoint later.",
                    importance_hint="normal",
                    created_at="2026-04-20T10:10:00+00:00",
                    session_id="run_active",
                    usefulness_score=0.0,
                ),
                RetrievalCandidate(
                    episode_id="ep-worker",
                    space_type="project-space",
                    event_type="conversation_turn",
                    summary="conversation_turn: The OpenClaw pilot uses a dedicated memory worker for background jobs.",
                    raw_text="assistant: The OpenClaw pilot uses a dedicated memory worker for background jobs.",
                    importance_hint="normal",
                    created_at="2026-04-20T09:30:00+00:00",
                    session_id="run_old",
                    usefulness_score=0.0,
                ),
            ],
            active_session_id="run_active",
        )

        self.assertEqual(ranked[0].episode_id, "ep-worker")

    def test_select_candidates_for_brief_excludes_session_items_for_durable_project_query(self) -> None:
        from app.services.retrieval import RetrievalCandidate, RetrievalService

        ranked = RetrievalService.rank_candidates(
            query="What durable project context should I keep in mind for the memory runtime?",
            candidates=[
                RetrievalCandidate(
                    episode_id="ep-session-scratch",
                    space_type="session-space",
                    event_type="conversation_turn",
                    summary="conversation_turn: Temporary naming experiment: maybe rename the runtime endpoint later.",
                    raw_text="assistant: Temporary naming experiment: maybe rename the runtime endpoint later.",
                    importance_hint="normal",
                    created_at="2026-04-20T10:10:00+00:00",
                    session_id="run_active",
                    usefulness_score=0.0,
                ),
                RetrievalCandidate(
                    episode_id="ep-stack",
                    space_type="project-space",
                    event_type="conversation_turn",
                    summary="conversation_turn: The memory runtime uses Postgres, Redis, and pgvector as the baseline stack.",
                    raw_text="assistant: The memory runtime uses Postgres, Redis, and pgvector as the baseline stack.",
                    importance_hint="normal",
                    created_at="2026-04-20T09:00:00+00:00",
                    session_id="run_old",
                    usefulness_score=0.0,
                ),
            ],
            active_session_id="run_active",
        )

        selected = RetrievalService.select_candidates_for_brief(
            query="What durable project context should I keep in mind for the memory runtime?",
            ranked_candidates=ranked,
            active_session_id="run_active",
            context_budget_tokens=900,
        )

        self.assertEqual([candidate.episode_id for candidate in selected], ["ep-stack"])

    def test_rank_candidates_prefers_integration_memory_for_integration_query(self) -> None:
        from app.services.retrieval import RetrievalCandidate, RetrievalService

        ranked = RetrievalService.rank_candidates(
            query="Which integration surfaces already exist for the memory runtime?",
            candidates=[
                RetrievalCandidate(
                    episode_id="ep-architecture",
                    space_type="project-space",
                    event_type="architecture_decision",
                    summary="architecture_decision: We decided to keep the memory runtime Python-first architecture for v1.",
                    raw_text="assistant: We decided to keep the memory runtime Python-first architecture for v1.",
                    importance_hint="high",
                    created_at="2026-04-20T09:00:00+00:00",
                    session_id="run_1",
                    usefulness_score=0.0,
                ),
                RetrievalCandidate(
                    episode_id="ep-integration",
                    space_type="project-space",
                    event_type="conversation_turn",
                    summary="conversation_turn: The runtime exposes adapter APIs for OpenClaw and BunkerAI.",
                    raw_text="assistant: The runtime exposes adapter APIs for OpenClaw and BunkerAI.",
                    importance_hint="normal",
                    created_at="2026-04-20T08:00:00+00:00",
                    session_id="run_1",
                    usefulness_score=0.0,
                ),
            ],
            active_session_id=None,
        )

        self.assertEqual(ranked[0].episode_id, "ep-integration")

    def test_rank_candidates_penalizes_scratch_storage_for_primary_runtime_query(self) -> None:
        from app.services.retrieval import RetrievalCandidate, RetrievalService

        ranked = RetrievalService.rank_candidates(
            query="What primary runtime storage should I keep in mind?",
            candidates=[
                RetrievalCandidate(
                    episode_id="ep-stack",
                    space_type="project-space",
                    event_type="conversation_turn",
                    summary="conversation_turn: The memory runtime uses Postgres, Redis, and pgvector as the baseline stack.",
                    raw_text="assistant: The memory runtime uses Postgres, Redis, and pgvector as the baseline stack.",
                    importance_hint="normal",
                    created_at="2026-04-20T09:00:00+00:00",
                    session_id="run_1",
                    usefulness_score=0.0,
                ),
                RetrievalCandidate(
                    episode_id="ep-scratch",
                    space_type="project-space",
                    event_type="conversation_turn",
                    summary="conversation_turn: SQLite is only for local scratch experiments and not the primary runtime database.",
                    raw_text="assistant: SQLite is only for local scratch experiments and not the primary runtime database.",
                    importance_hint="normal",
                    created_at="2026-04-20T10:00:00+00:00",
                    session_id="run_1",
                    usefulness_score=0.0,
                ),
            ],
            active_session_id=None,
        )

        self.assertEqual(ranked[0].episode_id, "ep-stack")

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
                usefulness_score=0.0,
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
                usefulness_score=0.0,
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
                usefulness_score=0.0,
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
                usefulness_score=0.0,
            ),
        ]

        brief = RetrievalService.build_memory_brief(ranked)

        fixture_path = (
            Path(__file__).resolve().parents[1] / "fixtures" / "golden" / "recall_brief_expected.json"
        )
        expected = json.loads(fixture_path.read_text())

        self.assertEqual(brief, expected)

    def test_collect_selected_space_types_preserves_shared_space(self) -> None:
        from app.services.retrieval import RetrievalCandidate, RetrievalService

        selected = RetrievalService.collect_selected_space_types(
            [
                RetrievalCandidate(
                    episode_id="ep-shared",
                    space_type="shared-space",
                    event_type="architecture_decision",
                    summary="architecture_decision: Shared stack uses Postgres and Redis.",
                    raw_text="assistant: Shared stack uses Postgres and Redis.",
                    importance_hint="high",
                    created_at="2026-04-20T09:00:00+00:00",
                    session_id="run_a",
                    usefulness_score=0.0,
                ),
                RetrievalCandidate(
                    episode_id="ep-agent",
                    space_type="agent-core",
                    event_type="policy_update",
                    summary="policy_update: Keep private formatting guidance isolated.",
                    raw_text="assistant: Keep private formatting guidance isolated.",
                    importance_hint="normal",
                    created_at="2026-04-20T09:05:00+00:00",
                    session_id="run_b",
                    usefulness_score=0.0,
                ),
                RetrievalCandidate(
                    episode_id="ep-shared-2",
                    space_type="shared-space",
                    event_type="conversation_turn",
                    summary="conversation_turn: Shared deployment notes.",
                    raw_text="assistant: Shared deployment notes.",
                    importance_hint="normal",
                    created_at="2026-04-20T09:10:00+00:00",
                    session_id="run_c",
                    usefulness_score=0.0,
                ),
            ]
        )

        self.assertEqual(selected, ["shared-space", "agent-core"])

    def test_build_selection_explanations_reports_decisive_signal(self) -> None:
        from app.services.retrieval import RetrievalCandidate, RetrievalService

        candidate = RetrievalCandidate(
            episode_id="ep-policy",
            space_type="agent-core",
            event_type="policy_update",
            summary="policy_update: Always produce concise architecture summaries before implementation details.",
            raw_text="assistant: Always produce concise architecture summaries before implementation details.",
            importance_hint="high",
            created_at="2026-04-20T09:30:00+00:00",
            session_id="run_0",
            usefulness_score=0.0,
        )

        explanations = RetrievalService.build_selection_explanations(
            "How should the agent present architecture updates?",
            [candidate],
            active_session_id="run_123",
        )

        self.assertEqual(explanations[0].episode_id, "ep-policy")
        self.assertEqual(explanations[0].slot, "standing_procedures")
        self.assertEqual(explanations[0].decisive_signal, "procedural_policy")
        self.assertIn("procedural or policy-style query", explanations[0].why)
