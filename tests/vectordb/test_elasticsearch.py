import unittest
from unittest.mock import patch

from embedchain.vectordb.elasticsearch import ElasticsearchDB


class ElasticsearchDBTest(unittest.TestCase):

    def setUp(self):
        self.es_client = patch("elasticsearch.Elasticsearch")
        self.es_client.start()

        self.es_db = ElasticsearchDB()

    def tearDown(self):
        self.es_client.stop()

    def test_constructor(self):
        es_db = ElasticsearchDB()
        self.assertIsNotNone(es_db.client)

    def test_get_index(self):
        index = self.es_db._get_index()
        self.assertEqual(index, "my_collection_128")

    def test_initialize(self):
        self.es_db.initialize()
        self.assertTrue(self.es_client.indices.exists(index=self.es_db._get_index()))

    def test_get(self):
        document = {"text": "This is a test document."}
        self.es_db.add([document])

        self.assertEqual(self.es_db.get(ids=["1"]), ["1"])

    def test_add(self):
        document = {"text": "This is a test document."}
        self.es_db.add([document])

        document = self.es_db.get(ids=["1"])[0]
        self.assertEqual(document["text"], "This is a test document.")

    def test_query(self):
        documents = [
            {"text": "This is the first document."},
            {"text": "This is the second document."},
        ]
        self.es_db.add(documents)

        results = self.es_db.query(input_query=["This is the first document."], n_results=1)
        self.assertEqual(results, ["This is the first document."])

    def test_set_collection_name(self):
        self.es_db.set_collection_name("my_new_collection")
        self.assertEqual(self.es_db.config.collection_name, "my_new_collection")

    def test_count(self):
        documents = [
            {"text": "This is the first document."},
            {"text": "This is the second document."},
        ]
        self.es_db.add(documents)

        count = self.es_db.count()
        self.assertEqual(count, 2)

    def test_reset(self):
        self.es_db.reset()
        self.assertFalse(self.es_client.indices.exists(index=self.es_db._get_index()))

