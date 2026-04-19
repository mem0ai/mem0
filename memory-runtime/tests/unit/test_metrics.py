from __future__ import annotations

import unittest

from app.telemetry.metrics import render_prometheus_metrics


class MetricsRenderingTests(unittest.TestCase):
    def test_render_prometheus_metrics_includes_metadata_and_labels(self) -> None:
        rendered = render_prometheus_metrics(
            counters={
                "recall_requests_total": 2,
                "jobs_failed_total": 1,
            },
            job_status_counts={"pending": 3, "completed": 5},
            job_type_status_counts={
                ("memory_consolidation", "completed"): 2,
                ("memory_decay", "pending"): 1,
            },
        )

        self.assertIn("# HELP memory_runtime_recall_requests_total Total recall requests handled by the runtime.", rendered)
        self.assertIn("# TYPE memory_runtime_recall_requests_total counter", rendered)
        self.assertIn("memory_runtime_recall_requests_total 2", rendered)
        self.assertIn('memory_runtime_job_status{status="pending"} 3', rendered)
        self.assertIn(
            'memory_runtime_job_status_by_type{job_type="memory_consolidation",status="completed"} 2',
            rendered,
        )
