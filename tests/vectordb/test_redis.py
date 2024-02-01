import unittest

from mock import patch

from embedchain import App
from embedchain.config import AppConfig
from embedchain.config.vectordb.pinecone import PineconeDBConfig
from embedchain.embedder.base import BaseEmbedder
from embedchain.vectordb.redis import RedisDB


def mock_embedding_fn(texts: list[str]) -> list[list[float]]:
    """A mock embedding function."""
    return [[1, 2, 3], [4, 5, 6]]


class TestRedisDB(unittest.TestCase):
    def test_incorrect_config_throws_error(self):
        """Test the init method of the Redis class throws error for incorrect config"""
        with self.assertRaises(TypeError):
            RedisDB(config=PineconeDBConfig())

    @patch("embedchain.vectordb.redis.SearchIndex")
    def test_initialize(self, redis_client_mock):
        # Set the embedder
        embedder = BaseEmbedder()
        embedder.set_vector_dimension(3)
        embedder.set_embedding_fn(mock_embedding_fn)

        # Create a Redis instance
        db = RedisDB()
        app_config = AppConfig(collect_metrics=False)
        App(config=app_config, db=db, embedding_model=embedder)

        self.assertEqual(db.config.collection_name, "embedchain_store")
        self.assertEqual(db.config.collection_name, db._get_or_create_collection())
        self.assertEqual(db.config.collection_name, db._schema.index.name)
        self.assertEqual(db._schema.index.name, db._schema.index.prefix)

    @patch("embedchain.vectordb.redis.SearchIndex")
    def test_get(self, redis_client_mock):
        # redis_client_mock.return_value.scroll.return_value = ([], None)

        # Set the embedder
        embedder = BaseEmbedder()
        embedder.set_vector_dimension(3)
        embedder.set_embedding_fn(mock_embedding_fn)

        # Create a Redis instance
        db = RedisDB()
        app_config = AppConfig(collect_metrics=False)
        App(config=app_config, db=db, embedding_model=embedder)

        resp = db.get(ids=[], where={})
        self.assertEqual(resp, {"ids": [], "metadatas": []})
        resp2 = db.get(ids=["123", "456"], where={"url": "https://ai.ai"})
        self.assertEqual(resp2, {"ids": [], "metadatas": []})

    @patch("embedchain.vectordb.redis.SearchIndex")
    def test_add(self, redis_client_mock):
        # redis_client_mock.return_value.scroll.return_value = ([], None)

        # Set the embedder
        embedder = BaseEmbedder()
        embedder.set_vector_dimension(3)
        embedder.set_embedding_fn(mock_embedding_fn)

        # Create a Redis instance
        db = RedisDB()
        app_config = AppConfig(collect_metrics=False)
        App(config=app_config, db=db, embedding_model=embedder)

        documents = ["This is a test document.", "This is another test document."]
        metadatas = [{}, {}]
        ids = ["123", "456"]
        db.add(documents, metadatas, ids)
        redis_client_mock.return_value.load.assert_called_once_with(
            data=[
                {
                    "id": "123",
                    "text": "This is a test document.",
                    "metadata": {},
                    "vector": [1, 2, 3],
                },
                {
                    "id": "456",
                    "text": "This is another test document.",
                    "metadata": {},
                    "vector": [4, 5, 6],
                },
            ],
            id_field="id",
            batch_size=db.BATCH_SIZE,
        )

    @patch("embedchain.vectordb.redis.SearchIndex")
    def test_query(self, redis_client_mock):
        # Set the embedder
        embedder = BaseEmbedder()
        embedder.set_vector_dimension(3)
        embedder.set_embedding_fn(mock_embedding_fn)

        # Create a Redis instance
        db = RedisDB()
        app_config = AppConfig(collect_metrics=False)
        App(config=app_config, db=db, embedding_model=embedder)

        search_response = [
            {"id": "123", "text": "This is a test document.", "$.metadata": "{}", "vector_distance": 0.3},
            {"id": "456", "text": "This is another document.", "$.metadata": "{}", "vector_distance": 0.4},
        ]

        # Configure the mock client to return the mocked response.
        redis_client_mock.return_value.query.return_value = search_response

        # Query the database for the documents that are most similar to the query "This is a document".
        query = ["This is a document"]
        results_without_citations = db.query(query, n_results=2, where={})
        expected_results_without_citations = ["This is a test document.", "This is another document."]
        self.assertEqual(results_without_citations, expected_results_without_citations)

        results_with_citations = db.query(query, n_results=2, where={}, citations=True)
        expected_results_with_citations = [
            ("This is a test document.", {"score": 0.3}),
            ("This is another document.", {"score": 0.4}),
        ]
        print(results_with_citations, expected_results_with_citations, flush=True)
        self.assertEqual(results_with_citations, expected_results_with_citations)

    @patch("embedchain.vectordb.redis.SearchIndex")
    def test_count(self, redis_client_mock):
        # Set the embedder
        embedder = BaseEmbedder()
        embedder.set_vector_dimension(3)
        embedder.set_embedding_fn(mock_embedding_fn)

        # Create a Redis instance
        db = RedisDB()
        app_config = AppConfig(collect_metrics=False)
        App(config=app_config, db=db, embedding_model=embedder)

        db.count()
        redis_client_mock.return_value.info.assert_called_once()

    @patch("embedchain.vectordb.redis.SearchIndex")
    def test_reset(self, redis_client_mock):
        # Set the embedder
        embedder = BaseEmbedder()
        embedder.set_vector_dimension(3)
        embedder.set_embedding_fn(mock_embedding_fn)

        # Create a Redis instance
        db = RedisDB()
        app_config = AppConfig(collect_metrics=False)
        App(config=app_config, db=db, embedding_model=embedder)

        db.reset()
        redis_client_mock.return_value.delete.assert_called_once_with(drop=True)


if __name__ == "__main__":
    unittest.main()
