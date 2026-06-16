from __future__ import annotations

from dataclasses import asdict, dataclass
from inspect import Parameter, signature
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional


QueryBuilder = Callable[[Mapping[str, Any]], str]


@dataclass(frozen=True)
class MemoryValidationFailure:
    """A memory that was not found in the top search results for its validation query."""

    memory_id: Optional[str]
    memory: str
    query: str
    returned_ids: List[Optional[str]]


@dataclass(frozen=True)
class MemoryValidationReport:
    """Retrieval validation summary returned by :class:`MemoryValidator`."""

    checked: int
    found: int
    retrieval_rate: float
    failures: List[MemoryValidationFailure]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class MemoryValidator:
    """Validate that stored memories can be recalled through the normal search path.

    The validator is intentionally read-only. It samples memories with ``get_all()``,
    runs ``search()`` for each generated query, and checks whether the source memory
    appears in the returned top-k results.
    """

    def __init__(self, memory: Any):
        if not hasattr(memory, "get_all") or not hasattr(memory, "search"):
            raise TypeError("memory must expose get_all() and search() methods")
        self.memory = memory

    def validate(
        self,
        *,
        filters: Optional[Dict[str, Any]] = None,
        user_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        run_id: Optional[str] = None,
        sample_size: int = 20,
        top_k: int = 5,
        query_builder: Optional[QueryBuilder] = None,
        get_all_kwargs: Optional[Dict[str, Any]] = None,
        search_kwargs: Optional[Dict[str, Any]] = None,
    ) -> MemoryValidationReport:
        """Run a recall check for sampled memories.

        Args:
            filters: Entity and metadata filters to pass to ``get_all`` and ``search``.
            user_id: Convenience shorthand merged into ``filters``.
            agent_id: Convenience shorthand merged into ``filters``.
            run_id: Convenience shorthand merged into ``filters``.
            sample_size: Number of stored memories to validate.
            top_k: Number of search results to inspect for each validation query.
            query_builder: Optional callable that receives a memory dict and returns
                the query to use. By default the memory text itself is used.
            get_all_kwargs: Extra keyword arguments for ``get_all``.
            search_kwargs: Extra keyword arguments for ``search``.

        Returns:
            MemoryValidationReport with aggregate retrieval rate and failed cases.
        """
        if sample_size <= 0:
            raise ValueError("sample_size must be greater than 0")
        if top_k <= 0:
            raise ValueError("top_k must be greater than 0")

        effective_filters = self._build_filters(filters, user_id=user_id, agent_id=agent_id, run_id=run_id)
        if not effective_filters:
            raise ValueError("filters, user_id, agent_id, or run_id is required to select memories")

        memories = self._sample_memories(effective_filters, sample_size, get_all_kwargs or {})
        build_query = query_builder or self._default_query_builder

        checked = 0
        found = 0
        failures: List[MemoryValidationFailure] = []

        for memory in memories:
            memory_text = self._memory_text(memory)
            if not memory_text:
                continue

            query = build_query(memory)
            if not isinstance(query, str) or not query.strip():
                raise ValueError("query_builder must return a non-empty string")

            checked += 1
            query = query.strip()
            source_id = self._memory_id(memory)
            search_results = self._search(query, effective_filters, top_k, search_kwargs or {})
            match_found = self._contains_memory(search_results, source_id, memory_text)

            if match_found:
                found += 1
            else:
                failures.append(
                    MemoryValidationFailure(
                        memory_id=source_id,
                        memory=memory_text,
                        query=query,
                        returned_ids=[self._memory_id(result) for result in search_results],
                    )
                )

        retrieval_rate = found / checked if checked else 0.0
        return MemoryValidationReport(
            checked=checked,
            found=found,
            retrieval_rate=retrieval_rate,
            failures=failures,
        )

    def _sample_memories(
        self, filters: Dict[str, Any], sample_size: int, get_all_kwargs: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        kwargs = {"filters": filters, **get_all_kwargs}

        if "top_k" not in kwargs and "page_size" not in kwargs:
            kwargs[self._get_all_limit_param()] = sample_size

        response = self.memory.get_all(**kwargs)
        memories = self._extract_results(response)
        return memories[:sample_size]

    def _search(
        self, query: str, filters: Dict[str, Any], top_k: int, search_kwargs: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        response = self.memory.search(query, filters=filters, top_k=top_k, **search_kwargs)
        return self._extract_results(response)

    def _get_all_limit_param(self) -> str:
        try:
            params = signature(self.memory.get_all).parameters
        except (TypeError, ValueError):
            return "top_k"

        if "top_k" in params:
            return "top_k"
        if "page_size" in params:
            return "page_size"
        if any(param.kind == Parameter.VAR_KEYWORD for param in params.values()):
            return "page_size"
        return "top_k"

    @staticmethod
    def _build_filters(
        filters: Optional[Dict[str, Any]],
        *,
        user_id: Optional[str],
        agent_id: Optional[str],
        run_id: Optional[str],
    ) -> Dict[str, Any]:
        effective_filters = dict(filters or {})
        for key, value in (("user_id", user_id), ("agent_id", agent_id), ("run_id", run_id)):
            if value is not None:
                effective_filters[key] = value
        return effective_filters

    @staticmethod
    def _extract_results(response: Any) -> List[Dict[str, Any]]:
        if isinstance(response, Mapping):
            results = response.get("results", [])
        else:
            results = response

        if results is None:
            return []
        if not isinstance(results, Iterable) or isinstance(results, (str, bytes)):
            raise TypeError("memory response results must be a list of memory dictionaries")

        normalized = []
        for item in results:
            if isinstance(item, Mapping):
                normalized.append(dict(item))
        return normalized

    @staticmethod
    def _memory_id(memory: Mapping[str, Any]) -> Optional[str]:
        memory_id = memory.get("id") or memory.get("memory_id")
        return str(memory_id) if memory_id is not None else None

    @staticmethod
    def _memory_text(memory: Mapping[str, Any]) -> str:
        for key in ("memory", "text", "data"):
            value = memory.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return ""

    @staticmethod
    def _default_query_builder(memory: Mapping[str, Any]) -> str:
        return MemoryValidator._memory_text(memory)

    def _contains_memory(
        self,
        search_results: List[Mapping[str, Any]],
        source_id: Optional[str],
        source_text: str,
    ) -> bool:
        for result in search_results:
            result_id = self._memory_id(result)
            if source_id is not None and result_id == source_id:
                return True
            if source_id is None and self._memory_text(result) == source_text:
                return True
        return False
