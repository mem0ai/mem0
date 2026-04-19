from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
import unittest


class LifecycleServiceContractTests(unittest.TestCase):
    def test_project_memory_decays_with_age(self) -> None:
        from app.services.lifecycle import LifecycleService

        now = datetime(2026, 4, 20, 12, 0, tzinfo=timezone.utc)
        unit = SimpleNamespace(
            freshness_score=1.0,
            importance_score=0.5,
            access_count=0,
            status="active",
            created_at=now - timedelta(days=7),
        )

        decision = LifecycleService.evaluate_transition(
            memory_unit=unit,
            space_type="project-space",
            now=now,
        )

        self.assertEqual(decision.action, "decayed")
        self.assertLess(decision.new_freshness_score, 1.0)
        self.assertEqual(decision.new_status, "active")

    def test_session_memory_past_ttl_is_archived(self) -> None:
        from app.services.lifecycle import LifecycleService

        now = datetime(2026, 4, 20, 12, 0, tzinfo=timezone.utc)
        unit = SimpleNamespace(
            freshness_score=0.9,
            importance_score=0.4,
            access_count=0,
            status="active",
            created_at=now - timedelta(days=3),
        )

        decision = LifecycleService.evaluate_transition(
            memory_unit=unit,
            space_type="session-space",
            now=now,
        )

        self.assertEqual(decision.action, "archived")
        self.assertEqual(decision.new_status, "archived")

    def test_stale_low_value_project_memory_is_evicted(self) -> None:
        from app.services.lifecycle import LifecycleService

        now = datetime(2026, 4, 20, 12, 0, tzinfo=timezone.utc)
        unit = SimpleNamespace(
            freshness_score=0.2,
            importance_score=0.1,
            access_count=0,
            status="active",
            created_at=now - timedelta(days=45),
        )

        decision = LifecycleService.evaluate_transition(
            memory_unit=unit,
            space_type="project-space",
            now=now,
        )

        self.assertEqual(decision.action, "evicted")
        self.assertEqual(decision.new_status, "evicted")
