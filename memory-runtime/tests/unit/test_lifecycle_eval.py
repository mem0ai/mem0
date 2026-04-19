from __future__ import annotations

import unittest
from pathlib import Path

from app.lifecycle_eval import load_scenarios, run_lifecycle_eval


class LifecycleEvalTests(unittest.TestCase):
    def test_run_lifecycle_eval_passes_golden_scenarios(self) -> None:
        fixture_path = (
            Path(__file__).resolve().parents[1]
            / "fixtures"
            / "evals"
            / "lifecycle_quality_scenarios.json"
        )

        report = run_lifecycle_eval(scenarios=load_scenarios(fixture_path))

        self.assertEqual(report["total"], 6)
        self.assertEqual(report["failed"], 0)
        self.assertEqual(report["passed"], 6)
        self.assertEqual(report["metrics"]["action_match_rate"], 1.0)
        self.assertEqual(report["metrics"]["status_match_rate"], 1.0)
        self.assertGreater(report["metrics"]["destructive_action_rate"], 0.0)
        self.assertGreater(report["metrics"]["mean_freshness_score"], 0.0)
        self.assertTrue(all(item["passed"] for item in report["results"]))
