from __future__ import annotations

import unittest


class ConsolidationServiceContractTests(unittest.TestCase):
    def test_infer_memory_attributes_for_project_decision(self) -> None:
        from app.services.consolidation import ConsolidationService

        kind, scope = ConsolidationService.infer_memory_attributes(
            space_type="project-space",
            event_type="architecture_decision",
            content="We chose Python-first architecture for the memory runtime.",
        )

        self.assertEqual(kind, "decision")
        self.assertEqual(scope, "long-term")

    def test_infer_memory_attributes_promotes_decision_like_project_turns(self) -> None:
        from app.services.consolidation import ConsolidationService

        kind, scope = ConsolidationService.infer_memory_attributes(
            space_type="project-space",
            event_type="conversation_turn",
            content="We decided to keep the memory runtime Python-first for v1.",
        )

        self.assertEqual(kind, "decision")
        self.assertEqual(scope, "long-term")

    def test_infer_memory_attributes_promotes_procedural_guidance(self) -> None:
        from app.services.consolidation import ConsolidationService

        kind, scope = ConsolidationService.infer_memory_attributes(
            space_type="project-space",
            event_type="conversation_turn",
            content="Always produce concise architecture summaries before implementation details.",
        )

        self.assertEqual(kind, "procedure")
        self.assertEqual(scope, "long-term")

    def test_build_memory_content_uses_summary_without_event_prefix(self) -> None:
        from app.services.consolidation import ConsolidationService

        content = ConsolidationService.build_memory_content(
            summary="architecture_decision: We chose Python-first architecture for the memory runtime."
        )

        self.assertEqual(content, "We chose Python-first architecture for the memory runtime.")

    def test_normalize_merge_key_is_stable(self) -> None:
        from app.services.consolidation import ConsolidationService

        left = ConsolidationService.normalize_merge_key(
            "We chose Python-first architecture for the memory runtime."
        )
        right = ConsolidationService.normalize_merge_key(
            "We   chose   Python-first   architecture for the memory runtime."
        )

        self.assertEqual(left, right)

    def test_normalize_merge_key_collapses_decision_prefix_variants(self) -> None:
        from app.services.consolidation import ConsolidationService

        left = ConsolidationService.normalize_merge_key(
            "We decided to keep the memory runtime Python-first for v1."
        )
        right = ConsolidationService.normalize_merge_key("Keep the memory runtime Python-first for v1.")

        self.assertEqual(left, right)

    def test_topic_key_detects_same_subject_across_negative_and_positive_statements(self) -> None:
        from app.services.consolidation import ConsolidationService

        left = ConsolidationService.topic_key("We use Postgres as the primary database for memory-runtime.")
        right = ConsolidationService.topic_key("We do not use Postgres as the primary database for memory-runtime.")

        self.assertEqual(left, right)
