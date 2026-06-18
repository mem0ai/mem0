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
