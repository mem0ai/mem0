"""Optional NeMo Flow integration for Mem0 memory clients."""

from __future__ import annotations

import asyncio
import copy
import inspect
import logging
from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import nemo_flow

logger = logging.getLogger(__name__)

_SESSION_KEYS = ("user_id", "agent_id", "run_id")
_RESERVED_IDENTITY_KEYS = {"filters", "provider"}
_memory_identity: ContextVar["MemoryIdentity | None"] = ContextVar("mem0_nemo_flow_identity", default=None)


@dataclass(frozen=True)
class MemoryIdentity:
    """Mem0 memory scope used by the NeMo Flow intercept."""

    user_id: str | None = None
    agent_id: str | None = None
    run_id: str | None = None
    filters: Mapping[str, Any] = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "MemoryIdentity":
        filters: dict[str, Any] = {}
        nested_filters = value.get("filters")
        if isinstance(nested_filters, Mapping):
            filters.update({str(key): item for key, item in nested_filters.items() if item is not None})

        for key, item in value.items():
            if key in _SESSION_KEYS or key in _RESERVED_IDENTITY_KEYS or item is None:
                continue
            filters[str(key)] = item

        return cls(
            user_id=_string_or_none(value.get("user_id")),
            agent_id=_string_or_none(value.get("agent_id")),
            run_id=_string_or_none(value.get("run_id")),
            filters=filters,
        )

    def search_filters(self) -> dict[str, Any]:
        filters = dict(self.filters)
        for key in _SESSION_KEYS:
            value = getattr(self, key)
            if value:
                filters[key] = value
        return filters

    def local_kwargs(self) -> dict[str, str]:
        return {key: value for key in _SESSION_KEYS if (value := getattr(self, key)) is not None}

    def has_scope(self) -> bool:
        return bool(self.search_filters())


@dataclass(frozen=True)
class NemoFlowTurnContext:
    """Context passed to a custom identity resolver."""

    llm_name: str
    request: "nemo_flow.LLMRequest"
    scope_metadata: Mapping[str, Any] | None


IdentityResolver = Callable[[NemoFlowTurnContext], MemoryIdentity | Mapping[str, Any] | None]
QueryExtractor = Callable[["nemo_flow.LLMRequest"], str | None]
InteractionExtractor = Callable[["nemo_flow.LLMRequest", "nemo_flow.Json"], Sequence[Mapping[str, Any]] | None]
MemoryFormatter = Callable[[Sequence[Mapping[str, Any]]], str]


@dataclass(frozen=True)
class NemoFlowMem0Config:
    """Configuration for the Mem0 NeMo Flow execution intercept."""

    name: str = "mem0.memory"
    priority: int = 50
    auto_recall: bool = True
    auto_capture: bool = True
    top_k: int = 5
    threshold: float | None = 0.1
    infer: bool = True
    metadata: Mapping[str, Any] | None = None
    fail_open: bool = True
    enable_observability: bool = True
    run_sync_in_thread: bool = False
    identity_resolver: IdentityResolver | None = None
    query_extractor: QueryExtractor | None = None
    interaction_extractor: InteractionExtractor | None = None
    memory_formatter: MemoryFormatter | None = None


class NemoFlowMem0Handle:
    """Registration handle returned by `install`."""

    def __init__(self, name: str, nemo_flow_module: Any, intercept: "_Mem0NemoFlowIntercept"):
        self.name = name
        self._nemo_flow = nemo_flow_module
        self._intercept = intercept
        self._active = True

    @property
    def active(self) -> bool:
        return self._active

    @property
    def intercept(
        self,
    ) -> Callable[
        [str, "nemo_flow.LLMRequest", Callable[["nemo_flow.LLMRequest"], Any]],
        Any,
    ]:
        return self._intercept

    def uninstall(self) -> bool:
        """Deregister the NeMo Flow execution intercept."""

        if not self._active:
            return False
        removed = self._nemo_flow.intercepts.deregister_llm_execution(self.name)
        self._active = False
        return bool(removed)


@contextmanager
def memory_scope(
    user_id: str | None = None,
    *,
    agent_id: str | None = None,
    run_id: str | None = None,
    thread_id: str | None = None,
    filters: Mapping[str, Any] | None = None,
    activate_runtime: bool = True,
) -> Iterator[MemoryIdentity]:
    """Set Mem0 identity for framework calls in the current lexical scope.

    When NeMo Flow is installed, this also activates a NeMo Flow scope stack so
    patched framework integrations can route LLM calls through the Mem0
    intercept without requiring application code to import NeMo Flow directly.
    The LangGraph-friendly ``thread_id`` argument is treated as Mem0 ``run_id``.
    """

    run_id = _resolve_run_id(run_id=run_id, thread_id=thread_id)
    identity = MemoryIdentity(user_id=user_id, agent_id=agent_id, run_id=run_id, filters=filters or {})
    token = _memory_identity.set(identity)
    nemo_flow_module = _maybe_load_nemo_flow() if activate_runtime else None
    scope_handle = (
        _push_memory_context_scope(nemo_flow_module, identity)
        if nemo_flow_module is not None and identity.has_scope()
        else None
    )
    try:
        yield identity
    finally:
        _pop_memory_context_scope(nemo_flow_module, scope_handle)
        _memory_identity.reset(token)


memory_context = memory_scope
mem0_context = memory_scope


def install(
    memory: Any,
    *,
    name: str = "mem0.memory",
    priority: int = 50,
    auto_recall: bool = True,
    auto_capture: bool = True,
    top_k: int = 5,
    threshold: float | None = 0.1,
    infer: bool = True,
    metadata: Mapping[str, Any] | None = None,
    fail_open: bool = True,
    enable_observability: bool = True,
    activate_runtime: bool = True,
    run_sync_in_thread: bool = False,
    identity_resolver: IdentityResolver | None = None,
    query_extractor: QueryExtractor | None = None,
    interaction_extractor: InteractionExtractor | None = None,
    memory_formatter: MemoryFormatter | None = None,
) -> NemoFlowMem0Handle:
    """Register Mem0 on NeMo Flow's non-streaming LLM execution path.

    The provided memory object can be a Mem0 `Memory`, `AsyncMemory`,
    `MemoryClient`, or `AsyncMemoryClient`. Install the optional dependency
    with `mem0ai[nemo_flow]`. NeMo Flow is imported only when this function is
    called so the integration remains optional for regular Mem0 users. When
    observability is enabled, the adapter records nested NeMo Flow scopes for
    recall and capture instead of standalone mark events.
    """

    nemo_flow = _load_nemo_flow()
    if activate_runtime:
        _activate_runtime(nemo_flow)
    config = NemoFlowMem0Config(
        name=name,
        priority=priority,
        auto_recall=auto_recall,
        auto_capture=auto_capture,
        top_k=top_k,
        threshold=threshold,
        infer=infer,
        metadata=metadata,
        fail_open=fail_open,
        enable_observability=enable_observability,
        run_sync_in_thread=run_sync_in_thread,
        identity_resolver=identity_resolver,
        query_extractor=query_extractor,
        interaction_extractor=interaction_extractor,
        memory_formatter=memory_formatter,
    )
    intercept = _Mem0NemoFlowIntercept(memory, config, nemo_flow)
    nemo_flow.intercepts.register_llm_execution(name, priority, intercept)
    return NemoFlowMem0Handle(name, nemo_flow, intercept)


install_mem0 = install


class _Mem0NemoFlowIntercept:
    def __init__(self, memory: Any, config: NemoFlowMem0Config, nemo_flow_module: Any):
        self.memory = memory
        self.config = config
        self._nemo_flow = nemo_flow_module

    async def __call__(
        self,
        llm_name: str,
        request: "nemo_flow.LLMRequest",
        next_call: Callable[["nemo_flow.LLMRequest"], Any],
    ) -> "nemo_flow.Json":
        identity = self._resolve_identity(llm_name, request)
        if identity is None or not identity.has_scope():
            return await next_call(request)

        request_for_call = request
        if self.config.auto_recall:
            try:
                request_for_call = await self._recall(request, identity)
            except Exception:
                if not self.config.fail_open:
                    raise
                logger.warning("Mem0 recall failed in NeMo Flow intercept", exc_info=True)

        response = await next_call(request_for_call)

        if self.config.auto_capture:
            try:
                await self._capture(request, response, identity)
            except Exception:
                if not self.config.fail_open:
                    raise
                logger.warning("Mem0 capture failed in NeMo Flow intercept", exc_info=True)

        return response

    def _resolve_identity(self, llm_name: str, request: "nemo_flow.LLMRequest") -> MemoryIdentity | None:
        scope_metadata = _current_scope_metadata(self._nemo_flow)
        context = NemoFlowTurnContext(llm_name=llm_name, request=request, scope_metadata=scope_metadata)

        if self.config.identity_resolver is not None:
            identity = _coerce_identity(self.config.identity_resolver(context))
            if identity is not None:
                return identity

        context_identity = _memory_identity.get()
        if context_identity is not None and context_identity.has_scope():
            return context_identity

        return _identity_from_metadata(scope_metadata)

    async def _recall(self, request: "nemo_flow.LLMRequest", identity: MemoryIdentity) -> "nemo_flow.LLMRequest":
        query_extractor = self.config.query_extractor or _default_query_extractor
        query = query_extractor(request)
        if not query:
            return request

        search_kwargs: dict[str, Any] = {
            "filters": identity.search_filters(),
            "top_k": self.config.top_k,
        }
        if self.config.threshold is not None:
            search_kwargs["threshold"] = self.config.threshold

        scope_handle = self._start_scope(
            "mem0.recall",
            "Retriever",
            input={
                "query_length": len(query),
                "top_k": self.config.top_k,
                "threshold": self.config.threshold,
            },
            metadata=_identity_observability_metadata(identity),
        )
        scope_output: dict[str, Any] = {"result_count": 0, "injected": False}

        try:
            result = await self._invoke(self.memory.search, query, **search_kwargs)
            memories = _extract_memory_results(result)
            if not memories:
                return request

            formatter = self.config.memory_formatter or _default_memory_formatter
            memory_text = formatter(memories)
            scope_output = {"result_count": len(memories), "injected": False}
            if not memory_text:
                return request

            content = _content_with_memory(request.content, memory_text)
            if content is request.content:
                return request
            scope_output = {"result_count": len(memories), "injected": True}
            return self._nemo_flow.LLMRequest(request.headers, content)
        except Exception as exc:
            scope_output = {"error_type": type(exc).__name__}
            raise
        finally:
            self._end_scope(scope_handle, output=scope_output)

    async def _capture(
        self,
        request: "nemo_flow.LLMRequest",
        response: "nemo_flow.Json",
        identity: MemoryIdentity,
    ) -> None:
        interaction_extractor = self.config.interaction_extractor or _default_interaction_extractor
        messages = interaction_extractor(request, response)
        if not messages:
            return

        add_kwargs: dict[str, Any] = {
            "metadata": _capture_metadata(identity, self.config.metadata),
            "infer": self.config.infer,
        }
        local_kwargs = identity.local_kwargs()
        if not local_kwargs:
            logger.debug("Skipping Mem0 capture because Memory.add needs user_id, agent_id, or run_id")
            return
        add_kwargs.update(local_kwargs)

        scope_handle = self._start_scope(
            "mem0.capture",
            "Custom",
            input={"message_count": len(messages), "infer": self.config.infer},
            metadata=_identity_observability_metadata(identity),
        )
        scope_output: dict[str, Any] = {"message_count": len(messages), "stored": False}
        try:
            await self._invoke(self.memory.add, list(messages), **add_kwargs)
            scope_output = {"message_count": len(messages), "stored": True}
        except Exception as exc:
            scope_output = {"message_count": len(messages), "stored": False, "error_type": type(exc).__name__}
            raise
        finally:
            self._end_scope(scope_handle, output=scope_output)

    async def _invoke(self, method: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        if inspect.iscoroutinefunction(method):
            return await method(*args, **kwargs)
        if self.config.run_sync_in_thread:
            return await asyncio.to_thread(method, *args, **kwargs)
        result = method(*args, **kwargs)
        if inspect.isawaitable(result):
            return await result
        return result

    def _start_scope(
        self,
        name: str,
        scope_type_name: str,
        *,
        input: Mapping[str, Any] | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> Any | None:
        if not self.config.enable_observability:
            return None

        try:
            scope_type = getattr(self._nemo_flow.ScopeType, scope_type_name)
            return self._nemo_flow.scope.push(
                name,
                scope_type,
                input=dict(input or {}),
                metadata={"integration": "mem0", **dict(metadata or {})},
            )
        except Exception:
            logger.debug("Failed to start NeMo Flow Mem0 scope", exc_info=True)
            return None

    def _end_scope(self, handle: Any | None, *, output: Mapping[str, Any] | None = None) -> None:
        if handle is None:
            return

        try:
            self._nemo_flow.scope.pop(handle, output=dict(output or {}))
        except Exception:
            logger.debug("Failed to end NeMo Flow Mem0 scope", exc_info=True)


def _load_nemo_flow() -> Any:
    try:
        import nemo_flow

        return nemo_flow
    except ImportError as exc:
        raise ImportError(
            "mem0.integrations.nemo_flow requires NeMo Flow. Install it with `mem0ai[nemo_flow]` "
            "in the process that owns the NeMo Flow runtime before calling install()."
        ) from exc


def _maybe_load_nemo_flow() -> Any | None:
    try:
        return _load_nemo_flow()
    except ImportError:
        return None


def activate_runtime() -> None:
    """Activate NeMo Flow in the current context without exposing its API."""

    _activate_runtime(_load_nemo_flow())


def _activate_runtime(nemo_flow_module: Any) -> None:
    try:
        nemo_flow_module.get_scope_stack()
    except Exception:
        logger.debug("Failed to activate NeMo Flow scope stack for Mem0 integration", exc_info=True)


def _push_memory_context_scope(nemo_flow_module: Any, identity: MemoryIdentity) -> Any | None:
    _activate_runtime(nemo_flow_module)
    try:
        return nemo_flow_module.scope.push(
            "mem0.memory",
            nemo_flow_module.ScopeType.Custom,
            metadata={"integration": "mem0", "mem0": _identity_scope_metadata(identity)},
        )
    except Exception:
        logger.debug("Failed to push NeMo Flow Mem0 memory context scope", exc_info=True)
        return None


def _pop_memory_context_scope(nemo_flow_module: Any | None, handle: Any | None) -> None:
    if nemo_flow_module is None or handle is None:
        return

    try:
        nemo_flow_module.scope.pop(handle)
    except Exception:
        logger.debug("Failed to pop NeMo Flow Mem0 memory context scope", exc_info=True)


def _current_scope_metadata(nemo_flow_module: Any) -> Mapping[str, Any] | None:
    try:
        handle = nemo_flow_module.scope.get_handle()
    except Exception:
        return None
    metadata = getattr(handle, "metadata", None) if handle is not None else None
    return metadata if isinstance(metadata, Mapping) else None


def _identity_from_metadata(metadata: Mapping[str, Any] | None) -> MemoryIdentity | None:
    if metadata is None:
        return None

    mem0_metadata = metadata.get("mem0")
    if isinstance(mem0_metadata, Mapping):
        return MemoryIdentity.from_mapping(mem0_metadata)

    memory_metadata = metadata.get("memory")
    if isinstance(memory_metadata, Mapping) and memory_metadata.get("provider") in (None, "mem0"):
        return MemoryIdentity.from_mapping(memory_metadata)

    if any(key in metadata for key in _SESSION_KEYS) or "filters" in metadata:
        return MemoryIdentity.from_mapping(metadata)

    return None


def _coerce_identity(identity: MemoryIdentity | Mapping[str, Any] | None) -> MemoryIdentity | None:
    if identity is None or isinstance(identity, MemoryIdentity):
        return identity
    if isinstance(identity, Mapping):
        return MemoryIdentity.from_mapping(identity)
    raise TypeError("identity_resolver must return MemoryIdentity, mapping, or None")


def _capture_metadata(identity: MemoryIdentity, metadata: Mapping[str, Any] | None) -> dict[str, Any]:
    captured = dict(metadata or {})
    for key, value in identity.search_filters().items():
        captured.setdefault(key, value)
    return captured


def _resolve_run_id(*, run_id: str | None, thread_id: str | None) -> str | None:
    if run_id is not None and thread_id is not None and run_id != thread_id:
        raise ValueError("run_id and thread_id cannot both be set to different values")
    return run_id if run_id is not None else thread_id


def _identity_scope_metadata(identity: MemoryIdentity) -> dict[str, Any]:
    metadata: dict[str, Any] = {}
    if identity.user_id is not None:
        metadata["user_id"] = identity.user_id
    if identity.agent_id is not None:
        metadata["agent_id"] = identity.agent_id
    if identity.run_id is not None:
        metadata["run_id"] = identity.run_id
    if identity.filters:
        metadata["filters"] = dict(identity.filters)
    return metadata


def _identity_observability_metadata(identity: MemoryIdentity) -> dict[str, Any]:
    filters = identity.search_filters()
    return {
        "filter_keys": sorted(filters),
        "has_user_id": identity.user_id is not None,
        "has_agent_id": identity.agent_id is not None,
        "has_run_id": identity.run_id is not None,
    }


def _default_query_extractor(request: "nemo_flow.LLMRequest") -> str | None:
    content = request.content
    if not isinstance(content, Mapping):
        return None

    messages = content.get("messages")
    if isinstance(messages, Sequence) and not isinstance(messages, (str, bytes)):
        for message in reversed(messages):
            if isinstance(message, Mapping) and message.get("role") == "user":
                text = _text_from_content(message.get("content"))
                if text:
                    return text

    for key in ("input", "prompt", "query"):
        text = _text_from_content(content.get(key))
        if text:
            return text
    return None


def _default_interaction_extractor(
    request: "nemo_flow.LLMRequest",
    response: "nemo_flow.Json",
) -> Sequence[Mapping[str, Any]] | None:
    user_text = _default_query_extractor(request)
    assistant_text = _assistant_text_from_response(response)
    if not user_text or not assistant_text:
        return None
    return (
        {"role": "user", "content": user_text},
        {"role": "assistant", "content": assistant_text},
    )


def _assistant_text_from_response(response: Any) -> str | None:
    if isinstance(response, str):
        return response
    if not isinstance(response, Mapping):
        return _text_from_content(getattr(response, "content", None))

    choices = response.get("choices")
    if isinstance(choices, Sequence) and not isinstance(choices, (str, bytes)) and choices:
        first = choices[0]
        if isinstance(first, Mapping):
            message = first.get("message")
            if isinstance(message, Mapping):
                text = _text_from_content(message.get("content"))
                if text:
                    return text
            text = _text_from_content(first.get("text"))
            if text:
                return text

    for key in ("output_text", "text", "content", "response"):
        text = _text_from_content(response.get(key))
        if text:
            return text

    output = response.get("output")
    if isinstance(output, Sequence) and not isinstance(output, (str, bytes)):
        return _text_from_content(output)
    return None


def _extract_memory_results(response: Any) -> list[Mapping[str, Any]]:
    if isinstance(response, Mapping):
        candidates = response.get("results", response.get("memories", []))
    else:
        candidates = response

    if not isinstance(candidates, Sequence) or isinstance(candidates, (str, bytes)):
        return []

    memories: list[Mapping[str, Any]] = []
    for candidate in candidates:
        if isinstance(candidate, Mapping):
            memories.append(candidate)
        elif isinstance(candidate, str):
            memories.append({"memory": candidate})
    return memories


def _default_memory_formatter(memories: Sequence[Mapping[str, Any]]) -> str:
    lines = []
    for memory in memories:
        text = _text_from_content(memory.get("memory") or memory.get("text") or memory.get("content"))
        if text:
            lines.append(f"- {text}")

    if not lines:
        return ""
    return "Relevant memories:\n" + "\n".join(lines)


def _content_with_memory(content: Mapping[str, Any], memory_text: str) -> Mapping[str, Any]:
    messages = content.get("messages")
    if not isinstance(messages, Sequence) or isinstance(messages, (str, bytes)):
        return content

    new_content = copy.deepcopy(dict(content))
    new_messages = list(copy.deepcopy(messages))
    insert_at = 0
    while insert_at < len(new_messages):
        message = new_messages[insert_at]
        if not isinstance(message, Mapping) or message.get("role") != "system":
            break
        insert_at += 1

    new_messages.insert(insert_at, {"role": "system", "content": memory_text})
    new_content["messages"] = new_messages
    return new_content


def _text_from_content(content: Any) -> str | None:
    if content is None:
        return None
    if isinstance(content, str):
        return content
    if isinstance(content, Mapping):
        for key in ("text", "content"):
            text = _text_from_content(content.get(key))
            if text:
                return text
        return None
    if isinstance(content, Sequence) and not isinstance(content, (str, bytes)):
        parts = [_text_from_content(item) for item in content]
        text = "\n".join(part for part in parts if part)
        return text or None
    return str(content)


def _string_or_none(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


__all__ = [
    "MemoryIdentity",
    "NemoFlowMem0Config",
    "NemoFlowMem0Handle",
    "NemoFlowTurnContext",
    "activate_runtime",
    "install",
    "install_mem0",
    "mem0_context",
    "memory_context",
    "memory_scope",
]
