import os
import sys
import types
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

if "fastapi_pagination" not in sys.modules:
    fastapi_pagination = types.ModuleType("fastapi_pagination")

    class _Params:
        def __init__(self, page=1, size=50):
            self.page = page
            self.size = size

    class _Page:
        def __init__(self, items, total, params):
            self.items = items
            self.total = total
            self.page = params.page
            self.size = params.size

        @classmethod
        def create(cls, items, total, params):
            return cls(items, total, params)

        def __class_getitem__(cls, item):
            return cls

    fastapi_pagination.Page = _Page
    fastapi_pagination.Params = _Params
    sys.modules["fastapi_pagination"] = fastapi_pagination

    fastapi_pagination_ext = types.ModuleType("fastapi_pagination.ext")
    fastapi_pagination_ext_sqlalchemy = types.ModuleType("fastapi_pagination.ext.sqlalchemy")
    fastapi_pagination_ext_sqlalchemy.paginate = lambda *args, **kwargs: None
    sys.modules["fastapi_pagination.ext"] = fastapi_pagination_ext
    sys.modules["fastapi_pagination.ext.sqlalchemy"] = fastapi_pagination_ext_sqlalchemy

from fastapi_pagination import Params

API_ROOT = Path(__file__).resolve().parents[1] / "openmemory" / "api"
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))
os.environ.setdefault("OPENAI_API_KEY", "test-key")

from openmemory.api.app.routers import config as config_router
from openmemory.api.app.routers import memories as memories_router


def test_default_configuration_exposes_reranker_and_custom_prompts():
    config = config_router.get_default_configuration()

    assert "mem0" in config
    assert "reranker" in config["mem0"]
    assert "custom_fact_extraction_prompt" in config["mem0"]
    assert "custom_update_memory_prompt" in config["mem0"]
    assert config["mem0"]["reranker"] is None


@pytest.mark.asyncio
async def test_semantic_memory_page_uses_mem0_search_and_returns_scores(monkeypatch):
    memory_id_1 = uuid4()
    memory_id_2 = uuid4()
    app_id = uuid4()
    now = datetime.now(UTC)

    fake_client = SimpleNamespace()
    fake_client.search_calls = []

    def fake_search(**kwargs):
        fake_client.search_calls.append(kwargs)
        return {
            "results": [
                {"id": str(memory_id_1), "score": 0.93},
                {"id": str(memory_id_2), "score": 0.61},
            ]
        }

    fake_client.search = fake_search
    monkeypatch.setattr(memories_router, "get_memory_client", lambda: fake_client)

    app = SimpleNamespace(id=app_id, name="automatos")
    cat_a = SimpleNamespace(id=uuid4(), name="Projects")
    cat_b = SimpleNamespace(id=uuid4(), name="Work")
    memory_a = SimpleNamespace(
        id=memory_id_1,
        content="User prefers concise project updates",
        state=memories_router.MemoryState.active,
        app_id=app_id,
        app=app,
        categories=[cat_a],
        created_at=now,
        metadata_={"tier": "global"},
    )
    memory_b = SimpleNamespace(
        id=memory_id_2,
        content="Agent-specific workflow preference",
        state=memories_router.MemoryState.active,
        app_id=app_id,
        app=app,
        categories=[cat_b],
        created_at=now,
        metadata_={"tier": "agent"},
    )

    query_chain = SimpleNamespace()
    query_chain.filter = lambda *args, **kwargs: query_chain
    query_chain.options = lambda *args, **kwargs: query_chain
    query_chain.all = lambda: [memory_a, memory_b]

    db = SimpleNamespace()
    db.query = lambda *args, **kwargs: query_chain

    user = SimpleNamespace(id=uuid4(), user_id="ws_123")
    page = memories_router._semantic_memory_page(
        db=db,
        user=user,
        params=Params(page=1, size=10),
        search_query="project updates",
        threshold=0.5,
        rerank=True,
        sort_column="score",
        sort_direction="desc",
        enforce_permissions=False,
    )

    assert page is not None
    assert len(page.items) == 2
    assert page.items[0].id == memory_id_1
    assert page.items[0].score == 0.93
    assert page.items[1].id == memory_id_2
    assert page.items[1].score == 0.61

    assert fake_client.search_calls == [
        {
            "query": "project updates",
            "user_id": "ws_123",
            "limit": 50,
            "threshold": 0.5,
            "rerank": True,
        }
    ]
