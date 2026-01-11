import importlib
import sys
import types
from unittest.mock import MagicMock

import pytest


DEFAULT_PROMPT_TEMPLATE = (
    "You are a smart assistant who understands entities and their types in a given text. "
    "If user message contains self reference such as 'I', 'me', 'my' etc. then use {user_id} "
    "as the source entity. Extract all the entities from the text. ***DO NOT*** answer the question "
    "itself if the given text is a question."
)


def _install_stub(monkeypatch, module_name, is_package=False, **attrs):
    module = types.ModuleType(module_name)
    if is_package:
        module.__path__ = []
    for key, value in attrs.items():
        setattr(module, key, value)
    monkeypatch.setitem(sys.modules, module_name, module)
    return module


@pytest.fixture
def stub_graph_modules(monkeypatch):
    _install_stub(monkeypatch, "langchain_neo4j", Neo4jGraph=object)
    _install_stub(monkeypatch, "rank_bm25", BM25Okapi=object)
    _install_stub(monkeypatch, "langchain_memgraph", is_package=True)
    _install_stub(monkeypatch, "langchain_memgraph.graphs", is_package=True)
    _install_stub(monkeypatch, "langchain_memgraph.graphs.memgraph", Memgraph=object)


@pytest.mark.parametrize(
    "module_name",
    [
        "mem0.memory.graph_memory",
        "mem0.memory.memgraph_memory",
    ],
)
def test_custom_search_prompt_overrides_default(stub_graph_modules, module_name):
    module = importlib.import_module(module_name)
    module = importlib.reload(module)
    graph_cls = module.MemoryGraph

    graph = graph_cls.__new__(graph_cls)
    graph.llm_provider = "openai"
    graph.llm = MagicMock()
    graph.llm.generate_response.return_value = {"tool_calls": []}
    graph.config = MagicMock()
    graph.config.graph_store.custom_search_prompt = None

    filters = {"user_id": "test-user"}
    graph._retrieve_nodes_from_data("Hello", filters)

    messages = graph.llm.generate_response.call_args.kwargs["messages"]
    assert messages[0]["content"] == DEFAULT_PROMPT_TEMPLATE.format(user_id=filters["user_id"])

    graph.llm.generate_response.reset_mock()
    graph.config.graph_store.custom_search_prompt = "Custom search prompt for USER_ID only."
    graph._retrieve_nodes_from_data("Hello", filters)

    messages = graph.llm.generate_response.call_args.kwargs["messages"]
    assert messages[0]["content"] == "Custom search prompt for test-user only."
