"""Strands Mem0 -- persistent long-term memory for Strands agents, backed by Mem0.

:class:`Mem0MemoryStore` is a Strands ``MemoryStore`` that plugs into the agent
loop via a :class:`~strands.memory.MemoryManager`, with automatic memory injection
and extraction. It implements both write sinks, so ``extraction`` uses Mem0's
server-side extraction (no extra model call).

For the explicit, model-called tool (``store`` / ``retrieve`` / ``get`` / ``delete``),
use the ``mem0_memory`` tool from ``strands-agents-tools``; a store and the tool can
share one Mem0 backend and namespace.
"""

from importlib.metadata import PackageNotFoundError, version

from mem0_strands.client import Mem0ServiceClient
from mem0_strands.store import Mem0MemoryStore

__all__ = [
    "Mem0MemoryStore",
    "Mem0ServiceClient",
]

try:
    __version__ = version("mem0-strands")
except PackageNotFoundError:  # pragma: no cover - only when running from a source tree
    __version__ = "0.0.0+unknown"
