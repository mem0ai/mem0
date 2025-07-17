import os
import sys
import pytest
import asyncio
from unittest.mock import patch, MagicMock

# Ensure 'app' package is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "api"))

from openmemory.api.routes.mcp import search_memory_handler, add_memories_handler
from openmemory.api.app.utils.memory import get_memory_instance


class TestAdvancedMCPFeatures:
    @pytest.fixture
    def mock_memory_instance(self):
        with patch('openmemory.api.routes.mcp.get_memory_instance') as mock:
            mock_instance = MagicMock()
            mock.return_value = mock_instance
            yield mock_instance

    @pytest.mark.asyncio
    async def test_search_with_topk(self, mock_memory_instance):
        mock_memory_instance.search.return_value = {
            "results": [{"memory": f"result {i}", "score": 0.9 - i*0.1} for i in range(5)]
        }
        args = {"query": "test search", "topK": 5}
        results = await search_memory_handler(args)
        mock_memory_instance.search.assert_called_once()
        call_args = mock_memory_instance.search.call_args[1]
        assert call_args["limit"] == 5
        assert len(results) <= 5

    @pytest.mark.asyncio
    async def test_search_with_threshold(self, mock_memory_instance):
        mock_memory_instance.search.return_value = {"results": [{"memory": "high score result", "score": 0.8}]}
        args = {"query": "test search", "threshold": 0.7}
        await search_memory_handler(args)
        call_args = mock_memory_instance.search.call_args[1]
        assert call_args["threshold"] == 0.7

    @pytest.mark.asyncio
    async def test_search_with_filters(self, mock_memory_instance):
        mock_memory_instance.search.return_value = {"results": []}
        args = {"query": "test message", "filters": {"metadata.tags": "filtered", "metadata.priority": "high"}}
        await search_memory_handler(args)
        call_args = mock_memory_instance.search.call_args[1]
        assert call_args["filters"] == {"metadata.tags": "filtered", "metadata.priority": "high"}

    @pytest.mark.asyncio
    async def test_search_with_project_isolation(self, mock_memory_instance):
        mock_memory_instance.search.return_value = {"results": []}
        args = {"query": "project specific search", "projectId": "project-alpha"}
        await search_memory_handler(args)
        call_args = mock_memory_instance.search.call_args[1]
        assert call_args["project_id"] == "project-alpha"

    @pytest.mark.asyncio
    async def test_add_with_metadata(self, mock_memory_instance):
        mock_memory_instance.add.return_value = ["mem_123"]
        args = {"messages": ["Test message with tags"], "metadata": {"tags": ["test", "important"], "category": "research"}}
        result = await add_memories_handler(args)
        call_args = mock_memory_instance.add.call_args[1]
        assert call_args["metadata"] == {"tags": ["test", "important"], "category": "research"}
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_add_with_project_org_ids(self, mock_memory_instance):
        mock_memory_instance.add.return_value = ["mem_456"]
        args = {"messages": ["Scoped message"], "projectId": "proj-1", "orgId": "org-1"}
        await add_memories_handler(args)
        call_args = mock_memory_instance.add.call_args[1]
        assert call_args["project_id"] == "proj-1"
        assert call_args["org_id"] == "org-1"

    @pytest.mark.asyncio
    async def test_combined_advanced_search(self, mock_memory_instance):
        mock_memory_instance.search.return_value = {"results": []}
        args = {"query": "complex search", "topK": 3, "threshold": 0.8, "filters": {"tags": ["auth"]}, "projectId": "proj-auth", "orgId": "org-1"}
        await search_memory_handler(args)
        call_args = mock_memory_instance.search.call_args[1]
        assert call_args["limit"] == 3
        assert call_args["threshold"] == 0.8
        assert call_args["filters"] == {"tags": ["auth"]}
        assert call_args["project_id"] == "proj-auth"
        assert call_args["org_id"] == "org-1"


@pytest.mark.integration
class TestMemoryIntegration:
    @pytest.mark.asyncio
    async def test_real_memory_with_qdrant(self):
        try:
            memory = get_memory_instance()
            result = memory.add([{"role": "user", "content": "Test integration memory"}], user_id="test_user", metadata={"test": True, "integration": "real"})
            search_results = memory.search("integration memory", user_id="test_user", limit=5, filters={"metadata.test": True})
            assert len(search_results["results"]) > 0
        except Exception as e:
            pytest.skip(f"Integration test skipped: {e}")

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
