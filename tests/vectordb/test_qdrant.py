import unittest
import uuid

from mock import patch
from qdrant_client.http import models
from qdrant_client.http.models import Batch

from embedchain import App
from embedchain.config import AppConfig
from embedchain.config.vectordb.pinecone import PineconeDBConfig
from embedchain.embedder.base import BaseEmbedder
from embedchain.vectordb.qdrant import QdrantDB


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
        embedder.set_vector_dimension(1526)

        # Create a Qdrant instance
        db = QdrantDB()
        app_config = AppConfig(collect_metrics=False)
        App(config=app_config, db=db, embedder=embedder)

        self.assertEqual(db.collection_name, "embedchain-store-1526")
        self.assertEqual(db.client, qdrant_client_mock.return_value)
        qdrant_client_mock.return_value.get_collections.assert_called_once()

    @patch("embedchain.vectordb.qdrant.QdrantClient")
    def test_get(self, qdrant_client_mock):
        qdrant_client_mock.return_value.scroll.return_value = ([], None)

        # Set the embedder
        embedder = BaseEmbedder()
        embedder.set_vector_dimension(1526)

        # Create a Qdrant instance
        db = QdrantDB()
        app_config = AppConfig(collect_metrics=False)
        App(config=app_config, db=db, embedder=embedder)

        resp = db.get(ids=[], where={})
        self.assertEqual(resp, {"ids": []})
        resp2 = db.get(ids=["123", "456"], where={"url": "https://ai.ai"})
        self.assertEqual(resp2, {"ids": []})

    @patch("embedchain.vectordb.qdrant.QdrantClient")
    @patch.object(uuid, "uuid4", side_effect=TEST_UUIDS)
    def test_add(self, uuid_mock, qdrant_client_mock):
        qdrant_client_mock.return_value.scroll.return_value = ([], None)

        # Set the embedder
        embedder = BaseEmbedder()
        embedder.set_vector_dimension(1526)

        # Create a Qdrant instance
        db = QdrantDB()
        app_config = AppConfig(collect_metrics=False)
        App(config=app_config, db=db, embedder=embedder)

        embeddings = [[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]]
        documents = ["This is a test document.", "This is another test document."]
        metadatas = [{}, {}]
        ids = ["123", "456"]
        skip_embedding = True
        db.add(embeddings, documents, metadatas, ids, skip_embedding)
        qdrant_client_mock.return_value.upsert.assert_called_once_with(
            collection_name="embedchain-store-1526",
            points=Batch(
                ids=["abc", "def"],
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
                vectors=embeddings,
            ),
        )

    @patch("embedchain.vectordb.qdrant.QdrantClient")
    def test_query(self, qdrant_client_mock):
        # Set the embedder
        embedder = BaseEmbedder()
        embedder.set_vector_dimension(1526)

        # Create a Qdrant instance
        db = QdrantDB()
        app_config = AppConfig(collect_metrics=False)
        App(config=app_config, db=db, embedder=embedder)

        # Query for the document.
        db.query(input_query=["This is a test document."], n_results=1, where={"doc_id": "123"}, skip_embedding=True)

        qdrant_client_mock.return_value.search.assert_called_once_with(
            collection_name="embedchain-store-1526",
            query_filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="payload.metadata.doc_id",
                        match=models.MatchValue(
                            value="123",
                        ),
                    )
                ]
            ),
            query_vector=["This is a test document."],
            limit=1,
        )

    @patch("embedchain.vectordb.qdrant.QdrantClient")
    def test_count(self, qdrant_client_mock):
        # Set the embedder
        embedder = BaseEmbedder()
        embedder.set_vector_dimension(1526)

        # Create a Qdrant instance
        db = QdrantDB()
        app_config = AppConfig(collect_metrics=False)
        App(config=app_config, db=db, embedder=embedder)

        db.count()
        qdrant_client_mock.return_value.get_collection.assert_called_once_with(collection_name="embedchain-store-1526")

    @patch("embedchain.vectordb.qdrant.QdrantClient")
    def test_reset(self, qdrant_client_mock):
        # Set the embedder
        embedder = BaseEmbedder()
        embedder.set_vector_dimension(1526)

        # Create a Qdrant instance
        db = QdrantDB()
        app_config = AppConfig(collect_metrics=False)
        App(config=app_config, db=db, embedder=embedder)

        db.reset()
        qdrant_client_mock.return_value.delete_collection.assert_called_once_with(
            collection_name="embedchain-store-1526"
        )


if __name__ == "__main__":
    unittest.main()
