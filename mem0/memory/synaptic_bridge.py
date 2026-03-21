import asyncio
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

try:
    from synaptic_memory.system import SynapticMemorySystem

    _SYNAPTIC_AVAILABLE = True
except ImportError:
    _SYNAPTIC_AVAILABLE = False


class SynapticBridge:
    """Thin async bridge between AsyncMemory and SynapticMemorySystem."""

    def __init__(self, db_dir: Optional[str] = None) -> None:
        self._db_dir = db_dir
        self._system: Optional[Any] = None
        self._lock = asyncio.Lock()

    async def _ensure(self) -> Optional[Any]:
        """Lazy-connect SynapticMemorySystem on first use."""
        if self._system is not None:
            return self._system
        if not _SYNAPTIC_AVAILABLE:
            return None
        async with self._lock:
            if self._system is not None:
                return self._system
            try:
                kwargs: Dict[str, Any] = {}
                if self._db_dir:
                    kwargs["db_dir"] = self._db_dir
                system = SynapticMemorySystem(**kwargs)
                await system.__aenter__()
                self._system = system
                logger.debug("SynapticMemorySystem connected")
            except Exception as e:
                logger.warning(f"Failed to connect SynapticMemorySystem: {e}")
                return None
        return self._system

    async def on_add(
        self,
        memory_id: str,
        content: str,
        context_memories: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        system = await self._ensure()
        if system is None:
            return
        try:
            await system.add_memory(
                memory_id=memory_id,
                content=content,
                context_memories=context_memories or [],
            )
        except Exception as e:
            logger.warning(f"SynapticBridge.on_add failed for {memory_id}: {e}")

    async def on_search(
        self,
        query: str,
        results: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        system = await self._ensure()
        if system is None:
            return results
        try:
            await system.on_search(query=query, results=results)
        except Exception as e:
            logger.warning(f"SynapticBridge.on_search failed: {e}")
        return results

    async def close(self) -> None:
        if self._system is not None:
            try:
                await self._system.__aexit__(None, None, None)
            except Exception as e:
                logger.warning(f"SynapticBridge.close failed: {e}")
            finally:
                self._system = None
