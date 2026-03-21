"""Synaptic memory integration for the MCP server.

Extracted from mcp_server.py to keep fork-specific code separate
and reduce merge conflicts when cherry-picking upstream commits.
"""

import asyncio
import json
import logging
import os

_synaptic = None
_synaptic_lock = asyncio.Lock()


async def _get_synaptic():
    global _synaptic
    if not os.environ.get("SYNAPTIC_ENABLED"):
        return None
    if _synaptic is not None:
        return _synaptic
    async with _synaptic_lock:
        if _synaptic is None:
            try:
                from synaptic_memory.system import SynapticMemorySystem
                s = SynapticMemorySystem()
                await s.connect()
                _synaptic = s
            except Exception as exc:
                logging.warning("Synaptic memory unavailable: %s", exc)
    return _synaptic


async def on_add(results):
    """Call after add_memories to track synapses."""
    synaptic = await _get_synaptic()
    if not synaptic:
        return
    for result in results:
        if result.get("event") in ("ADD", "UPDATE"):
            try:
                await synaptic.add_memory(result["id"], result["memory"])
            except Exception as exc:
                logging.warning("synaptic add_memory failed: %s", exc)


async def on_search(query, results):
    """Call after search_memory to re-rank via synaptic strength."""
    synaptic = await _get_synaptic()
    if not synaptic or not results:
        return results
    try:
        return await synaptic.on_search(query, results)
    except Exception as exc:
        logging.warning("synaptic on_search failed: %s", exc)
    return results


def register_tools(mcp):
    """Register synaptic MCP tools if SYNAPTIC_ENABLED is set."""
    if not os.environ.get("SYNAPTIC_ENABLED"):
        return

    @mcp.tool(description="Get synaptic memory statistics: synapse counts, average strength, PageRank, weakening synapses, and citation type breakdown. Only available when SYNAPTIC_ENABLED is set.")
    async def synaptic_stats() -> str:
        synaptic = await _get_synaptic()
        if not synaptic:
            return "Synaptic memory is not enabled. Set SYNAPTIC_ENABLED=true to activate."
        try:
            stats = await synaptic.get_stats()
            return json.dumps(stats, indent=2)
        except Exception as exc:
            logging.exception("Error getting synaptic stats: %s", exc)
            return f"Error getting synaptic stats: {exc}"

    @mcp.tool(description="View the synaptic network for a specific memory: its importance score, PageRank, inbound/outbound synapses, and strength values. Only available when SYNAPTIC_ENABLED is set.")
    async def synaptic_network(memory_id: str) -> str:
        synaptic = await _get_synaptic()
        if not synaptic:
            return "Synaptic memory is not enabled. Set SYNAPTIC_ENABLED=true to activate."
        try:
            network = await synaptic.get_network(memory_id)
            return json.dumps(network, indent=2, default=str)
        except Exception as exc:
            logging.exception("Error getting synaptic network: %s", exc)
            return f"Error getting synaptic network: {exc}"

    @mcp.tool(description="Run synaptic maintenance: decay weakening synapses and recalculate PageRank centrality scores. Call periodically to keep the synaptic network healthy. Only available when SYNAPTIC_ENABLED is set.")
    async def synaptic_maintain() -> str:
        synaptic = await _get_synaptic()
        if not synaptic:
            return "Synaptic memory is not enabled. Set SYNAPTIC_ENABLED=true to activate."
        try:
            decay_result = await synaptic.run_decay()
            pagerank_result = await synaptic.run_pagerank()
            replay_items = await synaptic.run_replay_check()
            return json.dumps({
                "decay": decay_result,
                "pagerank_updated": len(pagerank_result),
                "due_for_replay": len(replay_items),
            }, indent=2, default=str)
        except Exception as exc:
            logging.exception("Error running synaptic maintenance: %s", exc)
            return f"Error running synaptic maintenance: {exc}"
