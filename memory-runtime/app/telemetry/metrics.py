from __future__ import annotations

from collections import Counter
from threading import Lock


_METRIC_DEFINITIONS = {
    "consolidation_created_total": (
        "counter",
        "Total memory units created by consolidation.",
    ),
    "consolidation_merged_total": (
        "counter",
        "Total memory units merged by consolidation.",
    ),
    "jobs_processed_total": (
        "counter",
        "Total jobs processed successfully by the worker.",
    ),
    "jobs_failed_total": (
        "counter",
        "Total jobs failed during worker processing.",
    ),
    "lifecycle_decayed_total": (
        "counter",
        "Total memory units decayed by lifecycle rules.",
    ),
    "lifecycle_archived_total": (
        "counter",
        "Total memory units archived by lifecycle rules.",
    ),
    "lifecycle_evicted_total": (
        "counter",
        "Total memory units evicted by lifecycle rules.",
    ),
    "recall_requests_total": (
        "counter",
        "Total recall requests handled by the runtime.",
    ),
    "recall_candidates_total": (
        "counter",
        "Total recall candidates considered by the runtime.",
    ),
    "recall_selected_total": (
        "counter",
        "Total recall items selected into memory briefs.",
    ),
}
_KNOWN_COUNTERS = set(_METRIC_DEFINITIONS)
_COUNTERS: Counter[str] = Counter()
_LOCK = Lock()


def increment_metric(name: str, value: int = 1) -> None:
    with _LOCK:
        _COUNTERS[name] += value


def snapshot_metrics() -> dict[str, int]:
    with _LOCK:
        snapshot = {name: 0 for name in _KNOWN_COUNTERS}
        snapshot.update(_COUNTERS)
        return snapshot


def reset_metrics() -> None:
    with _LOCK:
        _COUNTERS.clear()


def render_prometheus_metrics(
    *,
    counters: dict[str, int] | None = None,
    job_status_counts: dict[str, int] | None = None,
    job_type_status_counts: dict[tuple[str, str], int] | None = None,
) -> str:
    metric_values = counters or snapshot_metrics()
    job_status_counts = job_status_counts or {}
    job_type_status_counts = job_type_status_counts or {}

    lines: list[str] = []
    for name in sorted(_METRIC_DEFINITIONS):
        metric_type, description = _METRIC_DEFINITIONS[name]
        metric_name = f"memory_runtime_{name}"
        lines.append(f"# HELP {metric_name} {description}")
        lines.append(f"# TYPE {metric_name} {metric_type}")
        lines.append(f"{metric_name} {metric_values.get(name, 0)}")

    lines.append("# HELP memory_runtime_job_status Current job count by status.")
    lines.append("# TYPE memory_runtime_job_status gauge")
    for status in sorted(job_status_counts):
        lines.append(f'memory_runtime_job_status{{status="{status}"}} {job_status_counts[status]}')

    lines.append("# HELP memory_runtime_job_status_by_type Current job count by type and status.")
    lines.append("# TYPE memory_runtime_job_status_by_type gauge")
    for job_type, status in sorted(job_type_status_counts):
        value = job_type_status_counts[(job_type, status)]
        lines.append(
            f'memory_runtime_job_status_by_type{{job_type="{job_type}",status="{status}"}} {value}'
        )

    return "\n".join(lines) + "\n"
