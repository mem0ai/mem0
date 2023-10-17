import unittest
from unittest.mock import patch

from embedchain import App
from embedchain.config import AppConfig
from embedchain.embedder.base import BaseEmbedder
from embedchain.vectordb.weaviate import WeaviateDB


class TestWeaviateDb(unittest.TestCase):
    @patch("embedchain.vectordb.weaviate.weaviate")
    def test_initialize(self, weaviate_mock):
        """Test the init method of the WeaviateDb class."""
        weaviate_client_mock = weaviate_mock.Client.return_value
        weaviate_client_schema_mock = weaviate_client_mock.schema

        # Mock that schema doesn't already exist so that a new schema is created
        weaviate_client_schema_mock.exists.return_value = False
        # Set the embedder
        embedder = BaseEmbedder()
        embedder.set_vector_dimension(1526)

        # Create a Weaviate instance
        db = WeaviateDB()
        app_config = AppConfig(collect_metrics=False)
        App(config=app_config, db=db, embedder=embedder)

        expected_class_obj = {
            "classes": [
                {
                    "class": "Embedchain_store_1526",
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
                            "dataType": ["Embedchain_store_1526_metadata"],
                        },
                    ],
                },
                {
                    "class": "Embedchain_store_1526_metadata",
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
                        {
                            "name": "text",
                            "dataType": ["text"],
                        },
                    ],
                },
            ]
        }

        # Assert that the Weaviate client was initialized
        weaviate_mock.Client.assert_called_once()
        self.assertEqual(db.index_name, "Embedchain_store_1526")
        weaviate_client_schema_mock.create.assert_called_once_with(expected_class_obj)

    @patch("embedchain.vectordb.weaviate.weaviate")
    def test_get_or_create_db(self, weaviate_mock):
        """Test the _get_or_create_db method of the WeaviateDb class."""
        weaviate_client_mock = weaviate_mock.Client.return_value

        embedder = BaseEmbedder()
        embedder.set_vector_dimension(1526)

        # Create a Weaviate instance
        db = WeaviateDB()
        app_config = AppConfig(collect_metrics=False)
        App(config=app_config, db=db, embedder=embedder)

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
        embedder.set_vector_dimension(1526)

        # Create a Weaviate instance
        db = WeaviateDB()
        app_config = AppConfig(collect_metrics=False)
        App(config=app_config, db=db, embedder=embedder)

        embeddings = [[1, 2, 3]]
        documents = ["This is a test document."]
        metadatas = [None]
        ids = ["123"]
        skip_embedding = True
        db.add(embeddings, documents, metadatas, ids, skip_embedding)

        # Check if the document was added to the database.
        weaviate_client_batch_mock.configure.assert_called_once_with(batch_size=100, timeout_retries=3)
        weaviate_client_batch_enter_mock.add_data_object.assert_any_call(
            data_object={"text": documents[0]}, class_name="Embedchain_store_1526_metadata"
        )

        weaviate_client_batch_enter_mock.add_data_object.assert_any_call(
            data_object={"identifier": ids[0], "text": documents[0]},
            class_name="Embedchain_store_1526",
            vector=embeddings[0],
        )

    @patch("embedchain.vectordb.weaviate.weaviate")
    def test_query(self, weaviate_mock):
        """Test the query method of the WeaviateDb class."""
        weaviate_client_mock = weaviate_mock.Client.return_value
        weaviate_client_query_mock = weaviate_client_mock.query
        weaviate_client_query_get_mock = weaviate_client_query_mock.get.return_value

        # Set the embedder
        embedder = BaseEmbedder()
        embedder.set_vector_dimension(1526)

        # Create a Weaviate instance
        db = WeaviateDB()
        app_config = AppConfig(collect_metrics=False)
        App(config=app_config, db=db, embedder=embedder)

        # Query for the document.
        db.query(input_query=["This is a test document."], n_results=1, where={}, skip_embedding=True)

        weaviate_client_query_mock.get.assert_called_once_with("Embedchain_store_1526", ["text"])
        weaviate_client_query_get_mock.with_near_vector.assert_called_once_with(
            {"vector": ["This is a test document."]}
        )

    @patch("embedchain.vectordb.weaviate.weaviate")
    def test_reset(self, weaviate_mock):
        """Test the reset method of the WeaviateDb class."""
        weaviate_client_mock = weaviate_mock.Client.return_value
        weaviate_client_batch_mock = weaviate_client_mock.batch

        # Set the embedder
        embedder = BaseEmbedder()
        embedder.set_vector_dimension(1526)

        # Create a Weaviate instance
        db = WeaviateDB()
        app_config = AppConfig(collect_metrics=False)
        App(config=app_config, db=db, embedder=embedder)

        # Reset the database.
        db.reset()

        weaviate_client_batch_mock.delete_objects.assert_called_once_with(
            "Embedchain_store_1526", where={"path": ["identifier"], "operator": "Like", "valueText": ".*"}
        )
