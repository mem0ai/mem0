"""Regression test for euclidean S3 Vectors score normalization."""

from unittest.mock import MagicMock

import pytest

from mem0.vector_stores.s3_vectors import S3Vectors


def test_issue_6546(monkeypatch):
    """Euclidean distances above one must retain distinct similarity scores."""
    mock_client = MagicMock()
    mock_client.get_vector_bucket.return_value = {}
    mock_client.get_index.return_value = {}
    mock_client.query_vectors.return_value = {
        "vectors": [
            {"key": "near", "distance": 1.5, "metadata": {}},
            {"key": "far", "distance": 3.0, "metadata": {}},
        ]
    }
    monkeypatch.setattr("mem0.vector_stores.s3_vectors.boto3.client", lambda *args, **kwargs: mock_client)

    store = S3Vectors(
        vector_bucket_name="test-bucket",
        collection_name="test-index",
        embedding_model_dims=3,
        distance_metric="euclidean",
    )

    results = store.search(query="test", vectors=[0.1, 0.2, 0.3], top_k=2)

    assert [result.id for result in results] == ["near", "far"]
    assert results[0].score == pytest.approx(1 / (1 + 1.5))
    assert results[1].score == pytest.approx(1 / (1 + 3.0))
    assert 0 < results[1].score < results[0].score <= 1
