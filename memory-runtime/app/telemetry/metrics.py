from __future__ import annotations

from collections import Counter
from threading import Lock


_KNOWN_COUNTERS = {
    "consolidation_created_total",
    "consolidation_merged_total",
    "jobs_processed_total",
    "lifecycle_decayed_total",
    "lifecycle_archived_total",
    "lifecycle_evicted_total",
}
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
