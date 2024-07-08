import unittest
from unittest.mock import patch

from embedchain import App
from embedchain.config import AppConfig
from embedchain.config.vector_db.pinecone import PineconeDBConfig
from embedchain.embedder.base import BaseEmbedder
from embedchain.vectordb.weaviate import WeaviateDB


def mock_embedding_fn(texts: list[str]) -> list[list[float]]:
    """A mock embedding function."""
    return [[1, 2, 3], [4, 5, 6]]


class TestWeaviateDb(unittest.TestCase):
    def test_incorrect_config_throws_error(self):
        """Test the init method of the WeaviateDb class throws error for incorrect config"""
        with self.assertRaises(TypeError):
            WeaviateDB(config=PineconeDBConfig())

    @patch("embedchain.vectordb.weaviate.weaviate")
    def test_initialize(self, weaviate_mock):
        """Test the init method of the WeaviateDb class."""
        weaviate_client_mock = weaviate_mock.Client.return_value
        weaviate_client_schema_mock = weaviate_client_mock.schema

        # Mock that schema doesn't already exist so that a new schema is created
        weaviate_client_schema_mock.exists.return_value = False
        # Set the embedder
        embedder = BaseEmbedder()
        embedder.set_vector_dimension(1536)
        embedder.set_embedding_fn(mock_embedding_fn)

        # Create a Weaviate instance
        db = WeaviateDB()
        app_config = AppConfig(collect_metrics=False)
        App(config=app_config, db=db, embedding_model=embedder)

        expected_class_obj = {
            "classes": [
                {
                    "class": "Embedchain_store_1536",
                    "vectorizer": "none",
                    "properties": [
                        {
                            "name": "identifier",
                            "dataType": ["text"],
                        },
                        {
                            "name": "text",
                            "dataType": ["text"],
                        },
                        {
                            "name": "metadata",
                            "dataType": ["Embedchain_store_1536_metadata"],
                        },
                    ],
                },
                {
                    "class": "Embedchain_store_1536_metadata",
                    "vectorizer": "none",
                    "properties": [
                        {
                            "name": "data_type",
                            "dataType": ["text"],
                        },
                        {
                            "name": "doc_id",
                            "dataType": ["text"],
                        },
                        {
                            "name": "url",
                            "dataType": ["text"],
                        },
                        {
                            "name": "hash",
                            "dataType": ["text"],
                        },
                        {
                            "name": "app_id",
                            "dataType": ["text"],
                        },
                    ],
                },
            ]
        }

        # Assert that the Weaviate client was initialized
        weaviate_mock.Client.assert_called_once()
        self.assertEqual(db.index_name, "Embedchain_store_1536")
        weaviate_client_schema_mock.create.assert_called_once_with(expected_class_obj)

    @patch("embedchain.vectordb.weaviate.weaviate")
    def test_get_or_create_db(self, weaviate_mock):
        """Test the _get_or_create_db method of the WeaviateDb class."""
        weaviate_client_mock = weaviate_mock.Client.return_value

        embedder = BaseEmbedder()
        embedder.set_vector_dimension(1536)
        embedder.set_embedding_fn(mock_embedding_fn)

        # Create a Weaviate instance
        db = WeaviateDB()
        app_config = AppConfig(collect_metrics=False)
        App(config=app_config, db=db, embedding_model=embedder)

        expected_client = db._get_or_create_db()
        self.assertEqual(expected_client, weaviate_client_mock)

    @patch("embedchain.vectordb.weaviate.weaviate")
    def test_add(self, weaviate_mock):
        """Test the add method of the WeaviateDb class."""
        weaviate_client_mock = weaviate_mock.Client.return_value
        weaviate_client_batch_mock = weaviate_client_mock.batch
        weaviate_client_batch_enter_mock = weaviate_client_mock.batch.__enter__.return_value

        # Set the embedder
        embedder = BaseEmbedder()
        embedder.set_vector_dimension(1536)
        embedder.set_embedding_fn(mock_embedding_fn)

        # Create a Weaviate instance
        db = WeaviateDB()
        app_config = AppConfig(collect_metrics=False)
        App(config=app_config, db=db, embedding_model=embedder)

        documents = ["This is test document"]
        metadatas = [None]
        ids = ["id_1"]
        db.add(documents, metadatas, ids)

        # Check if the document was added to the database.
        weaviate_client_batch_mock.configure.assert_called_once_with(batch_size=100, timeout_retries=3)
        weaviate_client_batch_enter_mock.add_data_object.assert_any_call(
            data_object={"text": documents[0]}, class_name="Embedchain_store_1536_metadata", vector=[1, 2, 3]
        )

        weaviate_client_batch_enter_mock.add_data_object.assert_any_call(
            data_object={"text": documents[0]},
            class_name="Embedchain_store_1536_metadata",
            vector=[1, 2, 3],
        )

    @patch("embedchain.vectordb.weaviate.weaviate")
    def test_query_without_where(self, weaviate_mock):
        """Test the query method of the WeaviateDb class."""
        weaviate_client_mock = weaviate_mock.Client.return_value
        weaviate_client_query_mock = weaviate_client_mock.query
        weaviate_client_query_get_mock = weaviate_client_query_mock.get.return_value

        # Set the embedder
        embedder = BaseEmbedder()
        embedder.set_vector_dimension(1536)
        embedder.set_embedding_fn(mock_embedding_fn)

        # Create a Weaviate instance
        db = WeaviateDB()
        app_config = AppConfig(collect_metrics=False)
        App(config=app_config, db=db, embedding_model=embedder)

        # Query for the document.
        db.query(input_query="This is a test document.", n_results=1, where={})

        weaviate_client_query_mock.get.assert_called_once_with("Embedchain_store_1536", ["text"])
        weaviate_client_query_get_mock.with_near_vector.assert_called_once_with({"vector": [1, 2, 3]})

    @patch("embedchain.vectordb.weaviate.weaviate")
    def test_query_with_where(self, weaviate_mock):
        """Test the query method of the WeaviateDb class."""
        weaviate_client_mock = weaviate_mock.Client.return_value
        weaviate_client_query_mock = weaviate_client_mock.query
        weaviate_client_query_get_mock = weaviate_client_query_mock.get.return_value
        weaviate_client_query_get_where_mock = weaviate_client_query_get_mock.with_where.return_value

        # Set the embedder
        embedder = BaseEmbedder()
        embedder.set_vector_dimension(1536)
        embedder.set_embedding_fn(mock_embedding_fn)

        # Create a Weaviate instance
        db = WeaviateDB()
        app_config = AppConfig(collect_metrics=False)
        App(config=app_config, db=db, embedding_model=embedder)

        # Query for the document.
        db.query(input_query="This is a test document.", n_results=1, where={"doc_id": "123"})

        weaviate_client_query_mock.get.assert_called_once_with("Embedchain_store_1536", ["text"])
        weaviate_client_query_get_mock.with_where.assert_called_once_with(
            {"operator": "Equal", "path": ["metadata", "Embedchain_store_1536_metadata", "doc_id"], "valueText": "123"}
        )
        weaviate_client_query_get_where_mock.with_near_vector.assert_called_once_with({"vector": [1, 2, 3]})

    @patch("embedchain.vectordb.weaviate.weaviate")
    def test_reset(self, weaviate_mock):
        """Test the reset method of the WeaviateDb class."""
        weaviate_client_mock = weaviate_mock.Client.return_value
        weaviate_client_batch_mock = weaviate_client_mock.batch

        # Set the embedder
        embedder = BaseEmbedder()
        embedder.set_vector_dimension(1536)
        embedder.set_embedding_fn(mock_embedding_fn)

        # Create a Weaviate instance
        db = WeaviateDB()
        app_config = AppConfig(collect_metrics=False)
        App(config=app_config, db=db, embedding_model=embedder)

        # Reset the database.
        db.reset()

        weaviate_client_batch_mock.delete_objects.assert_called_once_with(
            "Embedchain_store_1536", where={"path": ["identifier"], "operator": "Like", "valueText": ".*"}
        )

    @patch("embedchain.vectordb.weaviate.weaviate")
    def test_count(self, weaviate_mock):
        """Test the reset method of the WeaviateDb class."""
        weaviate_client_mock = weaviate_mock.Client.return_value
        weaviate_client_query = weaviate_client_mock.query

        # Set the embedder
        embedder = BaseEmbedder()
        embedder.set_vector_dimension(1536)
        embedder.set_embedding_fn(mock_embedding_fn)

        # Create a Weaviate instance
        db = WeaviateDB()
        app_config = AppConfig(collect_metrics=False)
        App(config=app_config, db=db, embedding_model=embedder)

        # Reset the database.
        db.count()

        weaviate_client_query.aggregate.assert_called_once_with("Embedchain_store_1536")
