import argparse
import asyncio
import json
import random
import tempfile
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List, Tuple

from mem0.memory.storage import SQLiteManager
from mem0.vector_stores.zvec import Zvec


def percentile(values: List[float], pct: float) -> float:
    if not values:
        return 0.0
    sorted_values = sorted(values)
    index = (len(sorted_values) - 1) * pct
    lower = int(index)
    upper = min(lower + 1, len(sorted_values) - 1)
    if lower == upper:
        return sorted_values[lower]
    lower_value = sorted_values[lower]
    upper_value = sorted_values[upper]
    return lower_value + (upper_value - lower_value) * (index - lower)


def summarize_latency_ms(values: List[float]) -> Dict[str, float]:
    if not values:
        return {"count": 0, "mean_ms": 0.0, "p50_ms": 0.0, "p95_ms": 0.0}
    return {
        "count": len(values),
        "mean_ms": mean(values),
        "p50_ms": percentile(values, 0.50),
        "p95_ms": percentile(values, 0.95),
    }


@dataclass
class WorkloadContext:
    store: Zvec
    dim: int
    id_lock: threading.Lock
    ids_lock: threading.Lock
    ids: List[str]


def make_vector(dim: int, seed: int) -> List[float]:
    rng = random.Random(seed)
    return [rng.random() for _ in range(dim)]


def add_operation(ctx: WorkloadContext, op_seed: int) -> float:
    memory_id = str(uuid.uuid4())
    vector = make_vector(ctx.dim, op_seed)
    payload = {
        "data": f"memory-{memory_id[:8]}",
        "user_id": "benchmark-user",
        "created_at": str(op_seed),
        "workload_tag": "mixed",
    }
    started = time.perf_counter()
    ctx.store.insert(vectors=[vector], payloads=[payload], ids=[memory_id])
    latency_ms = (time.perf_counter() - started) * 1000
    with ctx.ids_lock:
        ctx.ids.append(memory_id)
    return latency_ms


def update_operation(ctx: WorkloadContext, op_seed: int) -> float:
    with ctx.ids_lock:
        if not ctx.ids:
            return add_operation(ctx, op_seed)
        memory_id = random.choice(ctx.ids)
    updated_vector = make_vector(ctx.dim, op_seed + 17)
    payload = {
        "data": f"updated-{memory_id[:8]}",
        "user_id": "benchmark-user",
        "updated_at": str(op_seed),
        "workload_tag": "mixed",
    }
    started = time.perf_counter()
    ctx.store.update(vector_id=memory_id, vector=updated_vector, payload=payload)
    return (time.perf_counter() - started) * 1000


def delete_operation(ctx: WorkloadContext, op_seed: int) -> float:
    with ctx.ids_lock:
        if not ctx.ids:
            return add_operation(ctx, op_seed)
        index = random.randrange(len(ctx.ids))
        memory_id = ctx.ids.pop(index)
    started = time.perf_counter()
    ctx.store.delete(vector_id=memory_id)
    latency_ms = (time.perf_counter() - started) * 1000
    return latency_ms


def search_operation(ctx: WorkloadContext, op_seed: int) -> float:
    vector = make_vector(ctx.dim, op_seed)
    started = time.perf_counter()
    ctx.store.search(
        query="benchmark",
        vectors=vector,
        limit=10,
        filters={"user_id": "benchmark-user"},
    )
    return (time.perf_counter() - started) * 1000


def run_sync_mixed_workload(
    ctx: WorkloadContext,
    total_ops: int,
    read_ratio: float,
    thread_count: int,
    seed: int,
) -> Dict[str, Any]:
    write_latencies: List[float] = []
    search_latencies: List[float] = []
    operation_counts = {"add": 0, "update": 0, "delete": 0, "search": 0}

    rng = random.Random(seed + thread_count)

    def run_operation(op_index: int) -> Tuple[str, float]:
        if rng.random() < read_ratio:
            return "search", search_operation(ctx, op_index + seed)

        write_selector = op_index % 3
        if write_selector == 0:
            return "add", add_operation(ctx, op_index + seed)
        if write_selector == 1:
            return "update", update_operation(ctx, op_index + seed)
        return "delete", delete_operation(ctx, op_index + seed)

    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=thread_count) as executor:
        for op_name, latency in executor.map(run_operation, range(total_ops)):
            operation_counts[op_name] += 1
            if op_name == "search":
                search_latencies.append(latency)
            else:
                write_latencies.append(latency)
    elapsed = time.perf_counter() - started

    return {
        "mode": "sync",
        "threads": thread_count,
        "total_ops": total_ops,
        "elapsed_sec": elapsed,
        "throughput_ops_per_sec": (total_ops / elapsed) if elapsed else 0.0,
        "op_mix": operation_counts,
        "write_latency_ms": summarize_latency_ms(write_latencies),
        "search_latency_ms": summarize_latency_ms(search_latencies),
    }


async def run_async_to_thread_workload(
    ctx: WorkloadContext,
    total_ops: int,
    read_ratio: float,
    concurrency: int,
    seed: int,
) -> Dict[str, Any]:
    write_latencies: List[float] = []
    search_latencies: List[float] = []
    operation_counts = {"add": 0, "update": 0, "delete": 0, "search": 0}

    rng = random.Random(seed + 101)
    semaphore = asyncio.Semaphore(concurrency)

    async def run_operation(op_index: int):
        async with semaphore:
            if rng.random() < read_ratio:
                latency = await asyncio.to_thread(search_operation, ctx, op_index + seed)
                return "search", latency

            write_selector = op_index % 3
            if write_selector == 0:
                latency = await asyncio.to_thread(add_operation, ctx, op_index + seed)
                return "add", latency
            if write_selector == 1:
                latency = await asyncio.to_thread(update_operation, ctx, op_index + seed)
                return "update", latency
            latency = await asyncio.to_thread(delete_operation, ctx, op_index + seed)
            return "delete", latency

    started = time.perf_counter()
    results = await asyncio.gather(*(run_operation(i) for i in range(total_ops)))
    elapsed = time.perf_counter() - started

    for op_name, latency in results:
        operation_counts[op_name] += 1
        if op_name == "search":
            search_latencies.append(latency)
        else:
            write_latencies.append(latency)

    return {
        "mode": "async_to_thread",
        "concurrency": concurrency,
        "total_ops": total_ops,
        "elapsed_sec": elapsed,
        "throughput_ops_per_sec": (total_ops / elapsed) if elapsed else 0.0,
        "op_mix": operation_counts,
        "write_latency_ms": summarize_latency_ms(write_latencies),
        "search_latency_ms": summarize_latency_ms(search_latencies),
    }


def benchmark_sqlite_history_writes(total_writes: int) -> Dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="mem0_zvec_sqlite_") as tmp_dir:
        db_path = Path(tmp_dir) / "history.db"
        manager = SQLiteManager(str(db_path))
        latencies: List[float] = []
        started = time.perf_counter()
        for index in range(total_writes):
            memory_id = str(uuid.uuid4())
            t0 = time.perf_counter()
            manager.add_history(
                memory_id=memory_id,
                old_memory=None,
                new_memory=f"value-{index}",
                event="ADD",
                created_at=str(index),
                updated_at=str(index),
                is_deleted=0,
            )
            latencies.append((time.perf_counter() - t0) * 1000)
        elapsed = time.perf_counter() - started
        manager.close()

    return {
        "total_writes": total_writes,
        "elapsed_sec": elapsed,
        "throughput_writes_per_sec": (total_writes / elapsed) if elapsed else 0.0,
        "write_latency_ms": summarize_latency_ms(latencies),
    }


def preload_data(ctx: WorkloadContext, count: int, seed: int) -> None:
    for index in range(count):
        add_operation(ctx, seed + index)


def run_benchmark(args: argparse.Namespace) -> Dict[str, Any]:
    random.seed(args.seed)

    root_path = Path(args.path_root).expanduser().resolve()
    root_path.mkdir(parents=True, exist_ok=True)

    store = Zvec(
        collection_name=args.collection_name,
        embedding_model_dims=args.dim,
        path=str(root_path),
        read_only=False,
        enable_mmap=True,
    )
    store.reset()

    ctx = WorkloadContext(
        store=store,
        dim=args.dim,
        id_lock=threading.Lock(),
        ids_lock=threading.Lock(),
        ids=[],
    )

    preload_data(ctx, args.preload, args.seed)

    thread_counts = [int(item.strip()) for item in args.thread_counts.split(",") if item.strip()]
    sync_sweep = [
        run_sync_mixed_workload(
            ctx=ctx,
            total_ops=args.ops,
            read_ratio=args.read_ratio,
            thread_count=thread_count,
            seed=args.seed,
        )
        for thread_count in thread_counts
    ]

    async_result = asyncio.run(
        run_async_to_thread_workload(
            ctx=ctx,
            total_ops=args.ops,
            read_ratio=args.read_ratio,
            concurrency=args.async_concurrency,
            seed=args.seed,
        )
    )

    sqlite_result = benchmark_sqlite_history_writes(args.sqlite_writes)

    return {
        "config": {
            "path_root": str(root_path),
            "collection_name": args.collection_name,
            "dim": args.dim,
            "preload": args.preload,
            "ops": args.ops,
            "read_ratio": args.read_ratio,
            "thread_counts": thread_counts,
            "async_concurrency": args.async_concurrency,
            "sqlite_writes": args.sqlite_writes,
            "seed": args.seed,
        },
        "sync_thread_sweep": sync_sweep,
        "async_to_thread": async_result,
        "sqlite_history_write": sqlite_result,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Benchmark Mem0 Zvec mixed workload performance.")
    parser.add_argument("--path-root", default="/tmp/mem0_zvec_benchmark", help="Root directory for zvec collections.")
    parser.add_argument("--collection-name", default="mem0_benchmark", help="Benchmark collection name.")
    parser.add_argument("--dim", type=int, default=1536, help="Vector dimension.")
    parser.add_argument("--preload", type=int, default=200, help="Number of vectors to preload.")
    parser.add_argument("--ops", type=int, default=1000, help="Operation count for each benchmark scenario.")
    parser.add_argument("--read-ratio", type=float, default=0.6, help="Fraction of read(search) operations.")
    parser.add_argument("--thread-counts", default="1,2,4,8", help="Comma-separated sync thread counts.")
    parser.add_argument("--async-concurrency", type=int, default=16, help="Concurrent async to_thread tasks.")
    parser.add_argument("--sqlite-writes", type=int, default=1000, help="SQLite history write sample count.")
    parser.add_argument("--seed", type=int, default=7, help="Random seed.")
    parser.add_argument("--output-json", default="", help="Optional path to write JSON benchmark output.")
    return parser.parse_args()


if __name__ == "__main__":
    arguments = parse_args()
    benchmark_result = run_benchmark(arguments)
    result_json = json.dumps(benchmark_result, indent=2)
    print(result_json)
    if arguments.output_json:
        output_path = Path(arguments.output_json).expanduser().resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(result_json + "\n", encoding="utf-8")
