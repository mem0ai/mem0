"""Prometheus metric definitions shared across API and workers."""

from prometheus_client import Counter, Gauge, Histogram

SEARCH_LATENCY = Histogram(
    "mcp_search_latency_seconds",
    "Latency of MCP search_memory calls",
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
)
EMBED_CACHE_HIT = Counter("embed_cache_hit_total", "Embedding cache hits")
EMBED_CACHE_MISS = Counter("embed_cache_miss_total", "Embedding cache misses")
SEARCH_CACHE_HIT = Counter("search_cache_hit_total", "Search result cache hits")
SEARCH_CACHE_MISS = Counter("search_cache_miss_total", "Search result cache misses")
WRITE_QUEUE_DEPTH = Gauge("write_queue_depth", "Pending write queue jobs")
WRITE_WORKER_ERRORS = Counter("write_worker_error_total", "Write worker processing errors")
WRITE_WORKER_SUCCESS = Counter("write_worker_success_total", "Write worker successful jobs")
# Fase 2 (task_05): replication failures while dual-writing to the migration
# target collection. Active-collection writes are unaffected by these.
DUAL_WRITE_ERRORS = Counter("dual_write_error_total", "Dual-write replication failures to migration target")
# Fase 2 (task_06/task_09): monotonic count of points copied by the migration worker.
MIGRATION_POINTS_COPIED = Counter("migration_points_copied_total", "Points copied to the migration target collection")
# Fase 2 (task_09): per-project size and how many projects exceed the promotion threshold.
PROJECT_MEMORY_COUNT = Gauge("project_memory_count", "Cataloged memory count per project", ["project"])
PROJECT_SIZE_OVER_THRESHOLD = Gauge("project_size_over_threshold", "Number of projects over the promotion threshold")

# Fase 3 governance metrics
GOVERNANCE_JOB_QUEUE_DEPTH = Gauge(
    "governance_job_queue_depth", "Pending governance jobs", ["job_type"]
)
GOVERNANCE_JOB_LATENCY = Histogram(
    "governance_job_latency_seconds",
    "Governance job processing latency",
    ["job_type"],
    buckets=(0.1, 0.5, 1.0, 5.0, 15.0, 60.0, 300.0),
)
GOVERNANCE_JOB_ERRORS = Counter(
    "governance_job_errors_total", "Governance job processing errors", ["job_type"]
)
GOVERNANCE_DEDUPED_TOTAL = Counter("governance_deduped_total", "Memories deduplicated by governance")
GOVERNANCE_PRUNED_TOTAL = Counter("governance_pruned_total", "Memories pruned by TTL governance")
GOVERNANCE_MERGED_TOTAL = Counter("governance_merged_total", "Semantic merges performed by governance")
GOVERNANCE_CONTRADICTIONS_RESOLVED_TOTAL = Counter(
    "governance_contradictions_resolved_total", "Contradictions resolved by governance"
)
GOVERNANCE_PURGED_TOTAL = Counter("governance_purged_total", "Memories permanently purged")
GOVERNANCE_REVERTED_TOTAL = Counter("governance_reverted_total", "Governance quarantines reverted")
GOVERNANCE_QUARANTINED_CURRENT = Gauge(
    "governance_quarantined_current", "Memories currently in quarantine"
)
GOVERNANCE_REVERT_RATE = Gauge(
    "governance_revert_rate", "Ratio of reverts to governance actions", ["job_type"]
)
RETRIEVAL_DUPLICATE_IN_TOPK_RATIO = Gauge(
    "retrieval_duplicate_in_topk_ratio", "Proxy duplicate ratio in search top-K"
)
RETRIEVAL_QUALITY_INDEX = Gauge("retrieval_quality_index", "LLM-judge retrieval quality index")
