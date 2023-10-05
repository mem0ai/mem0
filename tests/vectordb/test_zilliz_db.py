# ruff: noqa: E501

import os
from dotenv import load_dotenv

import unittest

from embedchain import App
from embedchain.config import ZillizDBConfig
from embedchain.vectordb.zilliz import ZillizVectorDB

load_dotenv()


# to run tests, provide the URI and TOKEN in .env file
class TestZillizVectorDBClient(unittest.TestCase):
    # def test_init_with_uri_and_token(self):
    #     """
    #     Test if the `ZillizVectorDB` instance is initialized with the correct uri and token values.
    #     """
    #     uri = os.getenv("ZILLIZ_CLOUD_URI")
    #     token = os.getenv("ZILLIZ_CLOUD_TOKEN")
    #     config = ZillizDBConfig(uri=uri, token=token)

    #     db = ZillizVectorDB(config=config)
    #     db_config = db.config
    #     self.assertEqual(db_config.uri, uri)
    #     self.assertEqual(db_config.token, token)

    def test_init_without_uri(self):
        # Make sure it's not loaded from env
        try:
            del os.environ["ZILLIZ_CLOUD_URI"]
        except KeyError:
            pass
        # Test if an exception is raised when ZILLIZ_CLOUD_URI is missing
        with self.assertRaises(AttributeError):
            ZillizVectorDB()

    def test_init_without_token(self):
        # Make sure it's not loaded from env
        try:
            del os.environ["ZILLIZ_CLOUD_TOKEN"]
        except KeyError:
            pass
        # Test if an exception is raised when ZILLIZ_CLOUD_TOKEN is missing
        with self.assertRaises(AttributeError):
            ZillizVectorDB()

    def test_init_invalid_cred(self):
        # Test if an exception is raised when provided invalid credentials
        with self.assertRaises(ValueError):
            uri = "ululululu"
            token = "random12345"
            config = ZillizDBConfig(uri=uri, token=token)
            ZillizVectorDB(config=config)


# if using free tier, run only one test function at a time while commenting other test functions
# if using free tier to test the below, then comment all the functions except the function you want to test
# class TestZillizDBCollection(unittest.TestCase):
#     def test_init_with_default_collection(self):
#         """
#         Test if the `App` instance is initialized with the correct default collection name.
#         """
#         uri = os.getenv("ZILLIZ_CLOUD_URI")
#         token = os.getenv("ZILLIZ_CLOUD_TOKEN")
#         config = ZillizDBConfig(uri=uri, token=token)
#         app = App(db=ZillizVectorDB(config=config))

#         self.assertEqual(app.db.config.collection_name, "embedchain_store")

#     # to run the below test, comment the above and below tests and uncomment the below test
#     def test_init_with_custom_collection(self):
#         """
#         Test if the `App` instance is initialized with the correct custom collection name.
#         """
#         uri = os.getenv("ZILLIZ_CLOUD_URI")
#         token = os.getenv("ZILLIZ_CLOUD_TOKEN")
#         config = ZillizDBConfig(uri=uri, token=token,collection_name="test_collection")
#         app = App(db=ZillizVectorDB(config=config))

#         self.assertEqual(app.db.config.collection_name, "test_collection")

# def test_set_collection_name(self):
#     """
#     Test if the `App` collection is correctly switched using the `set_collection_name` method.
#     """
#     uri = os.getenv("ZILLIZ_CLOUD_URI")
#     token = os.getenv("ZILLIZ_CLOUD_TOKEN")
#     config = ZillizDBConfig(uri=uri, token=token)
#     app = App(db=ZillizVectorDB(config=config))
#     app.set_collection_name("test_collection")

#     self.assertEqual(app.db.config.collection_name, "test_collection")

# def test_changes_encapsulated(self):
#     """
#     Test that changes to one collection do not affect the other collection
#     """

#     config = ZillizDBConfig(collection_name="test_collection_1")
#     app = App(db=ZillizVectorDB(config=config))

#     # Collection should be empty when created
#     self.assertEqual(app.db.count(), 0)

#     # 1536 vector dimension because by default OpenAI Embedder is used
#     example_embedding = [[0.0 for _ in range(1536)] for _ in range(1)]
#     data = [["id1"], ["doc1"], example_embedding]
#     app.db.collection.insert(data=data)
#     app.db.collection.load()
#     app.db.collection.flush()

#     # After adding, should contain one item
#     self.assertEqual(app.db.count(), 1)

#     app.set_collection_name("test_collection_2")
#     # New collection is empty
#     self.assertEqual(app.db.count(), 0)

#     # Adding to new collection should not effect existing collection
#     app.db.collection.insert(data=data)
#     app.db.collection.load()
#     app.db.collection.flush()

#     app.set_collection_name("test_collection_1")
#     # Should still be 1, not 2.
#     self.assertEqual(app.db.count(), 1)

# def test_collections_are_persistent(self):
#     """
#     Test that a collection can be picked up later.
#     """
#     # Start with a clean app, assuming the database is empty

#     config = ZillizDBConfig(collection_name="test_collection_1")
#     app = App(db=ZillizVectorDB(config=config))

#     # drops the test_collection_1 and creates new one
#     app.db.reset()

#     example_embedding = [[0.0 for _ in range(1536)] for _ in range(1)]
#     data = [["id1"], ["doc1"], example_embedding]

#     app.db.collection.insert(data=data)
#     app.db.collection.load()
#     app.db.collection.flush()
#     del app

#     config = ZillizDBConfig(collection_name="test_collection_1")
#     app = App(db=ZillizVectorDB(config=config))
#     self.assertEqual(app.db.count(), 1)
#     print(app.db.client.list_collections())

# def test_add_with_skip_embedding(self):
#     """
#     Test that changes to one collection do not affect the other collection
#     """
#     app = App(db=ZillizVectorDB())

#     # Collection should be empty when created
#     self.assertEqual(app.db.count(), 0)

#     example_embedding = [[0.0 for _ in range(1536)] for _ in range(1)]

#     app.db.add(
#         embeddings=example_embedding,
#         documents=["document"],
#         metadatas=[{"value": "somevalue"}],
#         ids=["id"],
#         skip_embedding=True,
#     )
#     # After adding, should contain one item
#     self.assertEqual(app.db.count(), 1)

#     # Validate if the get utility of the database is working as expected
#     data = app.db.get(["id"], limit=1)
#     expected_value = {
#         "ids": {"id"},
#     }
#     self.assertEqual(data, expected_value)

#     # Validate if the query utility of the database is working as expected
#     data = app.db.query(input_query=example_embedding, where="", n_results=1, skip_embedding=True)
#     expected_value = ["document"]
#     self.assertEqual(data, expected_value)


if __name__ == "__main__":
    unittest.main()
