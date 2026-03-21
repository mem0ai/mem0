"""CLI entry point for the synaptic memory system."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from typing import Any

from synaptic_memory.system import SynapticMemorySystem
from synaptic_memory.visualization import (
    format_metrics_summary,
    format_network_ascii,
    format_strength_report,
)


def _print_json(data: Any) -> None:
    print(json.dumps(data, indent=2, default=str))


async def cmd_add(args: argparse.Namespace) -> None:
    cited_ids: list[str] | None = None
    if args.cite:
        cited_ids = [cid.strip() for cid in args.cite.split(",") if cid.strip()]

    async with SynapticMemorySystem() as sys_:
        result = await sys_.add_memory(
            memory_id=args.memory_id,
            content=args.content,
            cited_ids=cited_ids,
        )

    print(f"Memory registered: {result['memory_id']}")
    print(f"  Synapses created : {result['synapses_created']}")
    print(f"  Outbound total   : {result['outbound_count']}")
    print(f"  Importance score : {result['importance_score']:.4f}")


async def cmd_network(args: argparse.Namespace) -> None:
    async with SynapticMemorySystem() as sys_:
        await sys_.get_network(args.memory_id)
        inbound = await sys_.synapse_db.get_inbound(args.memory_id)
        outbound = await sys_.synapse_db.get_outbound(args.memory_id)
        metrics = await sys_.memory_db.get(args.memory_id)

    from synaptic_memory.models import MemoryAugmented

    effective_metrics = metrics if metrics is not None else MemoryAugmented(memory_id=args.memory_id)
    output = format_network_ascii(
        memory_id=args.memory_id,
        inbound=inbound,
        outbound=outbound,
        metrics=effective_metrics,
        memory_texts={},
    )
    print(output)


async def cmd_decay(args: argparse.Namespace) -> None:
    async with SynapticMemorySystem() as sys_:
        stats = await sys_.run_decay()

    print("Decay cycle complete:")
    for key, value in stats.items():
        print(f"  {key:<24} {value}")


async def cmd_pagerank(args: argparse.Namespace) -> None:
    async with SynapticMemorySystem() as sys_:
        scores = await sys_.run_pagerank()

    if not scores:
        print("No memories in network.")
        return

    sorted_scores = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    print(f"PageRank scores ({len(sorted_scores)} memories):")
    for memory_id, score in sorted_scores[:20]:
        bar = "#" * int(score * 40)
        print(f"  {memory_id[:36]:<36}  {score:.6f}  {bar}")
    if len(sorted_scores) > 20:
        print(f"  ... and {len(sorted_scores) - 20} more")


async def cmd_replay(args: argparse.Namespace) -> None:
    async with SynapticMemorySystem() as sys_:
        due_items = await sys_.run_replay_check()

    if not due_items:
        print("No reviews due.")
        return

    print(f"{len(due_items)} review(s) due:\n")
    for item in due_items:
        print(f"  [{item.get('priority', 0.0):.3f}] {item.get('memory_id')} "
              f"  reason={item.get('reason')}  "
              f"presented={item.get('presented_count', 0)}")


async def cmd_stats(args: argparse.Namespace) -> None:
    async with SynapticMemorySystem() as sys_:
        stats = await sys_.get_stats()
        all_memories = await sys_.memory_db.get_all()

    output = format_metrics_summary(all_memories)
    print(output)
    print()
    print("System stats:")
    for key, value in stats.items():
        if key == "citation_type_counts":
            print(f"  {'citation_types':<24}")
            for ct, count in value.items():
                print(f"    {ct:<20} {count}")
        else:
            print(f"  {key:<24} {value}")


async def cmd_report(args: argparse.Namespace) -> None:
    top_n: int = args.top if hasattr(args, "top") and args.top else 10

    async with SynapticMemorySystem() as sys_:
        all_synapses = await sys_.synapse_db.get_all()

    if not all_synapses:
        print("No synapses in network.")
        return

    sorted_synapses = sorted(all_synapses, key=lambda s: s.strength, reverse=True)
    top = sorted_synapses[:top_n]
    output = format_strength_report(top, {})
    print(output)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="synaptic",
        description="Synaptic Memory System — citation tracking and strength layer for Mem0",
    )
    sub = parser.add_subparsers(dest="command", metavar="COMMAND")
    sub.required = True

    p_add = sub.add_parser("add", help="Register a memory and detect citations")
    p_add.add_argument("memory_id", help="Unique memory identifier")
    p_add.add_argument("content", help="Memory content text")
    p_add.add_argument("--cite", metavar="ID1,ID2,...", help="Comma-separated cited IDs")

    p_network = sub.add_parser("network", help="Show network graph for a memory")
    p_network.add_argument("memory_id", help="Memory ID to inspect")

    sub.add_parser("decay", help="Run decay cycle across all synapses")
    sub.add_parser("pagerank", help="Recalculate and display network centrality scores")
    sub.add_parser("replay", help="Check for due memory reviews")
    sub.add_parser("stats", help="Display system-wide statistics")

    p_report = sub.add_parser("report", help="Show top synapses by strength")
    p_report.add_argument("--top", type=int, default=10, metavar="N", help="Number of top synapses")

    return parser


def cli() -> None:
    parser = build_parser()
    args = parser.parse_args()

    handlers: dict[str, Any] = {
        "add": cmd_add,
        "network": cmd_network,
        "decay": cmd_decay,
        "pagerank": cmd_pagerank,
        "replay": cmd_replay,
        "stats": cmd_stats,
        "report": cmd_report,
    }

    handler = handlers.get(args.command)
    if handler is None:
        parser.print_help()
        sys.exit(1)

    try:
        asyncio.run(handler(args))
    except KeyboardInterrupt:
        sys.exit(0)
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    cli()
