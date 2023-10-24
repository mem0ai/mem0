import unittest

from mock import patch

from embedchain import App
from embedchain.config.vectordb.deeplake import DeeplakeDBConfig
from embedchain.vectordb.deeplake import DeeplakeDB


class TestDeeplakeDB(unittest.TestCase):
    DEEPLAKE_PATH = "/tmp/deeplake6"

    @patch("embedchain.vectordb.deeplake.VectorStore")
    def test_add(self, deeplake_mock):
        deeplake_db = DeeplakeDB(DeeplakeDBConfig(path=self.DEEPLAKE_PATH))
        App(db=deeplake_db)

        deeplake_client_mock = deeplake_mock.return_value
        embeddings = [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]
        documents = ["This is a document.", "This is another document."]
        metadatas = [{}, {}]
        ids = ["id1", "id2"]
        deeplake_db.add(embeddings=embeddings, documents=documents, metadatas=metadatas, ids=ids, skip_embedding=True)
        deeplake_client_mock.add.assert_called_once_with(
            text=documents, embedding=embeddings, metadata=[{"identifier": "id1"}, {"identifier": "id2"}]
        )

        deeplake_db.client.delete_by_path(path=self.DEEPLAKE_PATH)

    @patch("embedchain.vectordb.deeplake.VectorStore")
    def test_get(self, deeplake_mock):
        db = DeeplakeDB(DeeplakeDBConfig(path=self.DEEPLAKE_PATH))
        App(db=db)

        deeplake_client_mock = deeplake_mock.return_value
        deeplake_client_mock.__len__.return_value = 2

        resp = db.get(ids=[], where={})
        self.assertEqual(resp, {"ids": []})
        db.get(ids=["123", "456"], where={"url": "https://ai.ai"}, limit=3)
        deeplake_client_mock.search.assert_called_once_with(
            exec_option="python", filter={"metadata": {"url": "https://ai.ai"}}, k=3
        )

        db.client.delete_by_path(path=self.DEEPLAKE_PATH)

    @patch("embedchain.vectordb.deeplake.VectorStore")
    def test_query(self, deeplake_mock):
        db = DeeplakeDB(DeeplakeDBConfig(path=self.DEEPLAKE_PATH))
        App(db=db)

        deeplake_client_mock = deeplake_mock.return_value

        db.query(input_query=["This is a test document."], n_results=1, where={"doc_id": "123"}, skip_embedding=True)
        deeplake_client_mock.search.assert_called_once_with(
            embedding=["This is a test document."], exec_option="python", filter={"metadata": {"doc_id": "123"}}, k=1
        )

        db.client.delete_by_path(path=self.DEEPLAKE_PATH)

    @patch("embedchain.vectordb.deeplake.VectorStore")
    def test_count(self, deeplake_mock):
        db = DeeplakeDB(DeeplakeDBConfig(path=self.DEEPLAKE_PATH))
        App(db=db)

        deeplake_client_mock = deeplake_mock.return_value

        db.count()
        deeplake_client_mock.__len__.assert_called_once()

        db.client.delete_by_path(path=self.DEEPLAKE_PATH)

    @patch("embedchain.vectordb.deeplake.VectorStore")
    def test_reset(self, deeplake_mock):
        db = DeeplakeDB(DeeplakeDBConfig(path=self.DEEPLAKE_PATH))
        App(db=db)

        deeplake_client_mock = deeplake_mock.return_value

        db.reset()
        deeplake_client_mock.delete_by_path.assert_called_once_with(self.DEEPLAKE_PATH)

        db.client.delete_by_path(path=self.DEEPLAKE_PATH)
