"""Strands Mem0 -- persistent long-term memory for Strands agents, backed by Mem0.

:class:`Mem0MemoryStore` is a Strands ``MemoryStore`` that plugs into the agent
loop via a :class:`~strands.memory.MemoryManager`, with automatic memory injection
and extraction. It implements both write sinks, so ``extraction`` uses Mem0's
server-side extraction (no extra model call).

For the explicit, model-called tool (``store`` / ``retrieve`` / ``get`` / ``delete``),
use the ``mem0_memory`` tool from ``strands-agents-tools``; a store and the tool can
share one Mem0 backend and namespace.
"""

from strands_mem0.client import Mem0ServiceClient
from strands_mem0.store import Mem0MemoryStore, Mem0MemoryStoreConfig

__all__ = [
    "Mem0MemoryStore",
    "Mem0MemoryStoreConfig",
    "Mem0ServiceClient",
]

__version__ = "0.1.0"
