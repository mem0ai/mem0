# ruff: noqa: E501

import logging
from unittest.mock import patch

import pytest

from embedchain.config.vector_db.oceanbase import OceanBaseConfig
from embedchain.vectordb.oceanbase import OceanBaseVectorDB

logger = logging.getLogger(__name__)    

class TestOceanBaseVector:
    @pytest.fixture
    def mock_embedder(self, mocker):
        return mocker.Mock()
    
    @patch("embedchain.vectordb.oceanbase.ObVecClient", autospec=True)
    def test_query(self, mock_client, mock_embedder):
        ob_config = OceanBaseConfig(drop_old=True)
        ob = OceanBaseVectorDB(config=ob_config)
        ob.embedder = mock_embedder

        with patch.object(ob.client, "ann_search") as mock_search:
            mock_embedder.embedding_fn.return_value = ["query_vector"]
            mock_search.return_value = [
                (
                    'result_doc',
                    '{"url": "url_1", "doc_id": "doc_id_1"}',
                    0.0
                )
            ]

            query_result = ob.query(input_query="query_text", n_results=1, where={})

            assert query_result == ["result_doc"]

            query_result = ob.query(input_query="query_text", n_results=1, where={}, citations=True)

            assert query_result == [
                (
                    "result_doc",
                    {"url": "url_1", "doc_id": "doc_id_1", "score": 1.0}
                )
            ]
