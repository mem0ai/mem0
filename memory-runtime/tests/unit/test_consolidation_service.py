from __future__ import annotations

import unittest


class ConsolidationServiceContractTests(unittest.TestCase):
    def test_infer_memory_attributes_for_project_decision(self) -> None:
        from app.services.consolidation import ConsolidationService

        kind, scope = ConsolidationService.infer_memory_attributes(
            space_type="project-space",
            event_type="architecture_decision",
        )

        self.assertEqual(kind, "decision")
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
