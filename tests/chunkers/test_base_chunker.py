import hashlib
import unittest
from unittest.mock import MagicMock

from embedchain.chunkers.base_chunker import BaseChunker
from embedchain.models.data_type import DataType


class TestBaseChunker(unittest.TestCase):
    test_doc_id = "DocID"

    def setUp(self):
        self.text_splitter = MagicMock()
        self.chunker = BaseChunker(self.text_splitter)
        self.loader = MagicMock()
        self.app_id = "test_app"
        self.data_type = DataType.TEXT
        self.chunker.set_data_type(self.data_type)

    def test_create_chunks(self):
        self.text_splitter.split_text.return_value = ["Chunk 1", "Chunk 2"]
        self.loader.load_data.return_value = {
            "data": [{"content": "Content 1", "meta_data": {"url": "URL 1"}}],
            "doc_id": TestBaseChunker.test_doc_id,
        }

        result = self.chunker.create_chunks(self.loader, "test_src", self.app_id)
        expected_ids = [
            hashlib.sha256(("Chunk 1" + "URL 1").encode()).hexdigest(),
            hashlib.sha256(("Chunk 2" + "URL 1").encode()).hexdigest(),
        ]

        self.assertEqual(result["documents"], ["Chunk 1", "Chunk 2"])
        self.assertEqual(result["ids"], expected_ids)
        self.assertEqual(
            result["metadatas"],
            [
                {
                    "url": "URL 1",
                    "data_type": self.data_type.value,
                    "doc_id": f"{self.app_id}--{TestBaseChunker.test_doc_id}",
                },
                {
                    "url": "URL 1",
                    "data_type": self.data_type.value,
                    "doc_id": f"{self.app_id}--{TestBaseChunker.test_doc_id}",
                },
            ],
        )
        self.assertEqual(result["doc_id"], f"{self.app_id}--{TestBaseChunker.test_doc_id}")

    def test_get_chunks(self):
        self.text_splitter.split_text.return_value = ["Chunk 1", "Chunk 2"]

        content = "This is a test content."
        result = self.chunker.get_chunks(content)

        self.assertEqual(len(result), 2)
        self.assertEqual(result, ["Chunk 1", "Chunk 2"])

    def test_set_data_type(self):
        self.chunker.set_data_type(DataType.MDX)
        self.assertEqual(self.chunker.data_type, DataType.MDX)

    def test_get_word_count(self):
        documents = ["This is a test.", "Another test."]
        result = self.chunker.get_word_count(documents)
        self.assertEqual(result, 6)
