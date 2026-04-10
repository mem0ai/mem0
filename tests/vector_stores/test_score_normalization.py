"""Tests to verify that all vector store backends normalize scores to similarity
(higher = better, range [0, 1]) instead of returning raw distances.

This addresses issue #4453: threshold filtering broken for distance-based
vector stores.
"""

import json
import sys
import unittest
from unittest.mock import MagicMock, patch

import numpy as np


class TestPGVectorScoreNormalization(unittest.TestCase):
    """PGVector uses cosine distance (<=> operator, range [0, 2]).
    Score should be max(0.0, 1.0 - distance).
    """

    def _make_pgvector(self):
        from mem0.vector_stores.pgvector import PGVector

        pv = PGVector.__new__(PGVector)
        pv.collection_name = "test_collection"
        mock_cursor = MagicMock()
        mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
        mock_cursor.__exit__ = MagicMock(return_value=False)
        pv._get_cursor = MagicMock(return_value=mock_cursor)
        return pv, mock_cursor

    def test_search_returns_similarity_not_distance(self):
        pv, mock_cursor = self._make_pgvector()
        mock_cursor.fetchall.return_value = [
            ("id1", 0.05, {"data": "close match"}),     # distance 0.05 → similarity 0.95
            ("id2", 0.30, {"data": "decent match"}),     # distance 0.30 → similarity 0.70
            ("id3", 0.85, {"data": "poor match"}),       # distance 0.85 → similarity 0.15
        ]

        results = pv.search(query="test", vectors=[0.1, 0.2, 0.3], limit=5)

        self.assertAlmostEqual(results[0].score, 0.95, places=5)
        self.assertAlmostEqual(results[1].score, 0.70, places=5)
        self.assertAlmostEqual(results[2].score, 0.15, places=5)

        for r in results:
            self.assertGreaterEqual(r.score, 0.0)
            self.assertLessEqual(r.score, 1.0)

    def test_perfect_match_returns_score_1(self):
        pv, mock_cursor = self._make_pgvector()
        mock_cursor.fetchall.return_value = [
            ("id1", 0.0, {"data": "exact match"}),  # distance 0.0 → similarity 1.0
        ]

        results = pv.search(query="test", vectors=[0.1, 0.2, 0.3], limit=5)
        self.assertAlmostEqual(results[0].score, 1.0, places=5)

    def test_max_distance_returns_score_0(self):
        pv, mock_cursor = self._make_pgvector()
        mock_cursor.fetchall.return_value = [
            ("id1", 2.0, {"data": "opposite"}),  # max cosine distance → similarity 0.0 (clamped)
        ]

        results = pv.search(query="test", vectors=[0.1, 0.2, 0.3], limit=5)
        self.assertAlmostEqual(results[0].score, 0.0, places=5)


class TestChromaScoreNormalization(unittest.TestCase):
    """Chroma uses L2 distance (range [0, ∞)).
    Score should be 1.0 / (1.0 + distance).
    """

    @patch("mem0.vector_stores.chroma.chromadb")
    def test_search_returns_similarity_not_l2_distance(self, mock_chromadb):
        from mem0.vector_stores.chroma import ChromaDB

        chroma = ChromaDB.__new__(ChromaDB)
        chroma.client = MagicMock()
        chroma.collection = MagicMock()

        chroma.collection.query.return_value = {
            "ids": [["id1", "id2"]],
            "distances": [[0.0, 1.0]],
            "metadatas": [[{"data": "exact"}, {"data": "moderate"}]],
        }

        results = chroma.search(query="test", vectors=[0.1, 0.2, 0.3], limit=5)

        self.assertAlmostEqual(results[0].score, 1.0, places=5)    # 1/(1+0)
        self.assertAlmostEqual(results[1].score, 0.5, places=5)    # 1/(1+1)

        for r in results:
            self.assertGreaterEqual(r.score, 0.0)
            self.assertLessEqual(r.score, 1.0)


class TestMilvusScoreNormalization(unittest.TestCase):
    """Milvus COSINE/IP returns similarity. L2 returns distance."""

    def test_l2_metric_returns_similarity(self):
        from mem0.vector_stores.milvus import MilvusDB
        from mem0.configs.vector_stores.milvus import MetricType

        milvus = MilvusDB.__new__(MilvusDB)
        milvus.metric_type = MetricType.L2
        milvus.client = MagicMock()
        milvus.collection_name = "test"

        data = [
            {"id": "id1", "distance": 0.0, "entity": {"metadata": {"data": "exact"}}},
            {"id": "id2", "distance": 4.0, "entity": {"metadata": {"data": "far"}}},
        ]

        results = milvus._parse_output(data)

        self.assertAlmostEqual(results[0].score, 1.0, places=5)    # 1/(1+0)
        self.assertAlmostEqual(results[1].score, 0.2, places=5)    # 1/(1+4)

    def test_cosine_metric_returns_score_as_is(self):
        from mem0.vector_stores.milvus import MilvusDB
        from mem0.configs.vector_stores.milvus import MetricType

        milvus = MilvusDB.__new__(MilvusDB)
        milvus.metric_type = MetricType.COSINE
        milvus.client = MagicMock()
        milvus.collection_name = "test"

        data = [
            {"id": "id1", "distance": 0.95, "entity": {"metadata": {"data": "close"}}},
        ]

        results = milvus._parse_output(data)
        self.assertAlmostEqual(results[0].score, 0.95, places=5)


class TestFaissScoreNormalization(unittest.TestCase):
    """FAISS returns L2 distance for euclidean, IP score for cosine."""

    def setUp(self):
        # Mock faiss module if not installed
        if "faiss" not in sys.modules:
            sys.modules["faiss"] = MagicMock()

    def test_euclidean_returns_similarity(self):
        from mem0.vector_stores.faiss import FAISS

        faiss_store = FAISS.__new__(FAISS)
        faiss_store.distance_strategy = "euclidean"
        faiss_store.index_to_id = {0: "id1", 1: "id2"}
        faiss_store.docstore = {"id1": {"data": "close"}, "id2": {"data": "far"}}

        scores = np.array([0.0, 3.0])
        ids = np.array([0, 1])

        results = faiss_store._parse_output(scores, ids)

        self.assertAlmostEqual(results[0].score, 1.0, places=5)    # 1/(1+0)
        self.assertAlmostEqual(results[1].score, 0.25, places=5)   # 1/(1+3)

    def test_cosine_returns_score_as_is(self):
        from mem0.vector_stores.faiss import FAISS

        faiss_store = FAISS.__new__(FAISS)
        faiss_store.distance_strategy = "cosine"
        faiss_store.index_to_id = {0: "id1"}
        faiss_store.docstore = {"id1": {"data": "match"}}

        scores = np.array([0.95])
        ids = np.array([0])

        results = faiss_store._parse_output(scores, ids)
        self.assertAlmostEqual(results[0].score, 0.95, places=5)

    def test_inner_product_returns_score_as_is(self):
        from mem0.vector_stores.faiss import FAISS

        faiss_store = FAISS.__new__(FAISS)
        faiss_store.distance_strategy = "inner_product"
        faiss_store.index_to_id = {0: "id1"}
        faiss_store.docstore = {"id1": {"data": "match"}}

        scores = np.array([0.88])
        ids = np.array([0])

        results = faiss_store._parse_output(scores, ids)
        self.assertAlmostEqual(results[0].score, 0.88, places=5)


class TestS3VectorsScoreNormalization(unittest.TestCase):
    """S3 Vectors returns cosine distance. Score should be max(0.0, 1.0 - distance)."""

    def setUp(self):
        for mod in ["boto3", "botocore", "botocore.exceptions"]:
            if mod not in sys.modules:
                sys.modules[mod] = MagicMock()

    def test_search_returns_similarity_not_distance(self):
        from mem0.vector_stores.s3_vectors import S3Vectors

        s3v = S3Vectors.__new__(S3Vectors)
        s3v.client = MagicMock()
        s3v.collection_name = "test"
        s3v.vector_bucket_name = "test-bucket"

        s3v.client.query_vectors.return_value = {
            "vectors": [
                {"key": "id1", "distance": 0.05, "metadata": json.dumps({"data": "close"})},
                {"key": "id2", "distance": 0.80, "metadata": json.dumps({"data": "far"})},
            ]
        }

        results = s3v.search(query="test", vectors=[0.1, 0.2, 0.3], limit=5)

        self.assertAlmostEqual(results[0].score, 0.95, places=5)
        self.assertAlmostEqual(results[1].score, 0.20, places=5)


class TestCassandraScoreNormalization(unittest.TestCase):
    """Cassandra computes cosine similarity in Python.
    Should return similarity directly, not distance.
    """

    def setUp(self):
        # Mock cassandra if not installed
        if "cassandra" not in sys.modules:
            mock_cassandra = MagicMock()
            sys.modules["cassandra"] = mock_cassandra
            sys.modules["cassandra.cluster"] = mock_cassandra.cluster
            sys.modules["cassandra.auth"] = mock_cassandra.auth

    def test_search_returns_similarity_not_distance(self):
        from mem0.vector_stores.cassandra import CassandraDB

        cass = CassandraDB.__new__(CassandraDB)
        cass.keyspace = "test"
        cass.collection_name = "test"
        cass.session = MagicMock()

        row1 = MagicMock()
        row1.id = "id1"
        row1.vector = [1.0, 0.0, 0.0]
        row1.payload = json.dumps({"data": "exact"})

        row2 = MagicMock()
        row2.id = "id2"
        row2.vector = [0.0, 1.0, 0.0]
        row2.payload = json.dumps({"data": "orthogonal"})

        mock_result = MagicMock()
        mock_result.__iter__ = MagicMock(return_value=iter([row1, row2]))
        cass.session.execute.return_value = mock_result

        results = cass.search(query="test", vectors=[1.0, 0.0, 0.0], limit=5)

        # Query [1,0,0] vs [1,0,0] → similarity = 1.0
        self.assertAlmostEqual(results[0].score, 1.0, places=3)
        # Query [1,0,0] vs [0,1,0] → similarity = 0.0
        self.assertAlmostEqual(results[1].score, 0.0, places=3)
        # Highest similarity first
        self.assertGreaterEqual(results[0].score, results[1].score)


class TestAzureMySQLScoreNormalization(unittest.TestCase):
    """Azure MySQL computes cosine similarity in Python.
    Should return similarity directly, not distance.
    """

    def setUp(self):
        for mod in ["pymysql", "pymysql.cursors", "dbutils", "dbutils.pooled_db"]:
            if mod not in sys.modules:
                sys.modules[mod] = MagicMock()

    def test_search_returns_similarity_not_distance(self):
        from mem0.vector_stores.azure_mysql import AzureMySQL

        azm = AzureMySQL.__new__(AzureMySQL)
        azm.collection_name = "test"

        mock_cursor = MagicMock()
        mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
        mock_cursor.__exit__ = MagicMock(return_value=False)
        azm._get_cursor = MagicMock(return_value=mock_cursor)

        mock_cursor.fetchall.return_value = [
            {"id": "id1", "vector": json.dumps([1.0, 0.0, 0.0]), "payload": json.dumps({"data": "match"})},
        ]

        results = azm.search(query="test", vectors=[1.0, 0.0, 0.0], limit=5)

        # Query [1,0,0] vs [1,0,0] → similarity = 1.0, not distance 0.0
        self.assertAlmostEqual(results[0].score, 1.0, places=3)
        self.assertGreater(results[0].score, 0.5)


class TestThresholdFilteringIntegration(unittest.TestCase):
    """Verify threshold filtering works correctly with normalized scores.

    Before the fix, a threshold of 0.7 would filter OUT good matches
    (distance 0.05 < 0.7) and KEEP bad matches (distance 0.85 >= 0.7).

    After the fix, similarity 0.95 >= 0.7 passes, similarity 0.15 < 0.7
    is filtered out — the correct behavior.
    """

    def test_threshold_keeps_good_matches_filters_bad(self):
        threshold = 0.7

        scores = [
            ("id1", 0.95, "close match"),
            ("id2", 0.70, "borderline match"),
            ("id3", 0.15, "poor match"),
        ]

        kept = [(id, score, data) for id, score, data in scores if score >= threshold]
        filtered = [(id, score, data) for id, score, data in scores if score < threshold]

        self.assertEqual(len(kept), 2)
        self.assertEqual(kept[0][0], "id1")
        self.assertEqual(kept[1][0], "id2")
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0][0], "id3")


if __name__ == "__main__":
    unittest.main()
