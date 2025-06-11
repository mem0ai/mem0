import unittest
import uuid

from mock import patch
from qdrant_client.http import models
from qdrant_client.http.models import Batch

from embedchain import App
from embedchain.config import AppConfig
from embedchain.config.vector_db.pinecone import PineconeDBConfig
from embedchain.embedder.base import BaseEmbedder
from embedchain.vectordb.qdrant import QdrantDB


def mock_embedding_fn(texts: list[str]) -> list[list[float]]:
    """A mock embedding function."""
    return [[1, 2, 3], [4, 5, 6]]


class TestQdrantDB(unittest.TestCase):
    TEST_UUIDS = ["abc", "def", "ghi"]

    def test_incorrect_config_throws_error(self):
        """Test the init method of the Qdrant class throws error for incorrect config"""
        with self.assertRaises(TypeError):
            QdrantDB(config=PineconeDBConfig())

    @patch("embedchain.vectordb.qdrant.QdrantClient")
    def test_initialize(self, qdrant_client_mock):
        # Set the embedder
        embedder = BaseEmbedder()
        embedder.set_vector_dimension(1536)
        embedder.set_embedding_fn(mock_embedding_fn)

        # Create a Qdrant instance
        db = QdrantDB()
        app_config = AppConfig(collect_metrics=False)
        App(config=app_config, db=db, embedding_model=embedder)

        self.assertEqual(db.collection_name, "embedchain-store-1536")
        self.assertEqual(db.client, qdrant_client_mock.return_value)
        qdrant_client_mock.return_value.get_collections.assert_called_once()

    @patch("embedchain.vectordb.qdrant.QdrantClient")
    def test_get(self, qdrant_client_mock):
        qdrant_client_mock.return_value.scroll.return_value = ([], None)

        # Set the embedder
        embedder = BaseEmbedder()
        embedder.set_vector_dimension(1536)
        embedder.set_embedding_fn(mock_embedding_fn)

        # Create a Qdrant instance
        db = QdrantDB()
        app_config = AppConfig(collect_metrics=False)
        App(config=app_config, db=db, embedding_model=embedder)

        resp = db.get(ids=[], where={})
        self.assertEqual(resp, {"ids": [], "metadatas": []})
        resp2 = db.get(ids=["123", "456"], where={"url": "https://ai.ai"})
        self.assertEqual(resp2, {"ids": [], "metadatas": []})

    @patch("embedchain.vectordb.qdrant.QdrantClient")
    @patch.object(uuid, "uuid4", side_effect=TEST_UUIDS)
    def test_add(self, uuid_mock, qdrant_client_mock):
        qdrant_client_mock.return_value.scroll.return_value = ([], None)

        # Set the embedder
        embedder = BaseEmbedder()
        embedder.set_vector_dimension(1536)
        embedder.set_embedding_fn(mock_embedding_fn)

        # Create a Qdrant instance
        db = QdrantDB()
        app_config = AppConfig(collect_metrics=False)
        App(config=app_config, db=db, embedding_model=embedder)

        documents = ["This is a test document.", "This is another test document."]
        metadatas = [{}, {}]
        ids = ["123", "456"]
        db.add(documents, metadatas, ids)
        qdrant_client_mock.return_value.upsert.assert_called_once_with(
            collection_name="embedchain-store-1536",
            points=Batch(
                ids=["123", "456"],
                payloads=[
                    {
                        "identifier": "123",
                        "text": "This is a test document.",
                        "metadata": {"text": "This is a test document."},
                    },
                    {
                        "identifier": "456",
                        "text": "This is another test document.",
                        "metadata": {"text": "This is another test document."},
                    },
                ],
                vectors=[[1, 2, 3], [4, 5, 6]],
            ),
        )

    @patch("embedchain.vectordb.qdrant.QdrantClient")
    def test_query(self, qdrant_client_mock):
        # Set the embedder
        embedder = BaseEmbedder()
        embedder.set_vector_dimension(1536)
        embedder.set_embedding_fn(mock_embedding_fn)

        # Create a Qdrant instance
        db = QdrantDB()
        app_config = AppConfig(collect_metrics=False)
        App(config=app_config, db=db, embedding_model=embedder)

        # Query for the document.
        db.query(input_query="This is a test document.", n_results=1, where={"doc_id": "123"})

        qdrant_client_mock.return_value.search.assert_called_once_with(
            collection_name="embedchain-store-1536",
            query_filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="metadata.doc_id",
                        match=models.MatchValue(
                            value="123",
                        ),
                    )
                ]
            ),
            query_vector=[1, 2, 3],
            limit=1,
        )

    @patch("embedchain.vectordb.qdrant.QdrantClient")
    def test_count(self, qdrant_client_mock):
        # Set the embedder
        embedder = BaseEmbedder()
        embedder.set_vector_dimension(1536)
        embedder.set_embedding_fn(mock_embedding_fn)

        # Create a Qdrant instance
        db = QdrantDB()
        app_config = AppConfig(collect_metrics=False)
        App(config=app_config, db=db, embedding_model=embedder)

        db.count()
        qdrant_client_mock.return_value.get_collection.assert_called_once_with(collection_name="embedchain-store-1536")

    @patch("embedchain.vectordb.qdrant.QdrantClient")
    def test_reset(self, qdrant_client_mock):
        # Set the embedder
        embedder = BaseEmbedder()
        embedder.set_vector_dimension(1536)
        embedder.set_embedding_fn(mock_embedding_fn)

        # Create a Qdrant instance
        db = QdrantDB()
        app_config = AppConfig(collect_metrics=False)
        App(config=app_config, db=db, embedding_model=embedder)

        db.reset()
        qdrant_client_mock.return_value.delete_collection.assert_called_once_with(
            collection_name="embedchain-store-1536"
        )


if __name__ == "__main__":
    unittest.main()
