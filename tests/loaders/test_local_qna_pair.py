import hashlib
import unittest

from embedchain.loaders.local_qna_pair import LocalQnaPairLoader


class TestLocalQnaPairLoader(unittest.TestCase):
    def test_load_data(self):
        loader = LocalQnaPairLoader()

        question = "What is the capital of France?"
        answer = "The capital of France is Paris."

        content = (question, answer)
        result = loader.load_data(content)

        self.assertIn("doc_id", result)
        self.assertIn("data", result)
        url = "local"

        expected_content = f"Q: {question}\nA: {answer}"
        self.assertEqual(result["data"][0]["content"], expected_content)

        self.assertEqual(result["data"][0]["meta_data"]["url"], url)

        self.assertEqual(result["data"][0]["meta_data"]["question"], question)

        expected_doc_id = hashlib.sha256((expected_content + url).encode()).hexdigest()
        self.assertEqual(result["doc_id"], expected_doc_id)
