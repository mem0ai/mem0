"""Test AzureCosmosDBNoSql functionality."""

import pytest
from typing import Any, Dict, List, Tuple, Optional
from unittest.mock import MagicMock, patch
from mem0.vector_stores.azure_cosmos_db_no_sql import AzureCosmosDBNoSql, Constants, OutputData

# Constants for cosmos db collection
DATABASE_NAME = "vectorSearchDB"
COLLECTION_NAME = "vectorSearchContainer"
PARTITION_KEY_VALUE = "partition_key_value"
VECTOR_DIMENSION = 10

def get_vector_indexing_policy(vector_type: str) -> dict:
    return {
        "indexingMode": "consistent",
        "includedPaths": [{"path": "/*"}],
        "excludedPaths": [{"path": '/"_etag"/?'}],
        "vectorIndexes": [{"path": "/vector", "type": vector_type}],
        "fullTextIndexes": [{"path": "/text"}],
    }

def get_vector_properties(path: str, data_type: str, dimensions: int, distance_function: str):
    return {
        "path": path,
        "dataType": data_type,
        "dimensions": dimensions,
        "distanceFunction": distance_function,
    }

def get_vector_embedding_policy(path: str, data_type: str, dimensions: int, distance_function: str) -> dict:
    vector_properties = get_vector_properties(path, data_type, dimensions, distance_function)
    return {
        "vectorEmbeddings": [vector_properties]
    }


def get_vector_search_fields(text_field: str, vector_field: str) -> dict:
    return {
        Constants.TEXT_FIELD: text_field,
        Constants.VECTOR_FIELD: vector_field,
    }


def get_full_text_policy() -> dict:
    return {
        "defaultLanguage": "en-US",
        "fullTextPaths": [{"path": "/text", "language": "en-US"}],
    }


def make_mem0_payload(description: str, user_id: str, hash_val: str, created_at: str, **extra) -> dict:
    """Build a realistic mem0-style flat payload matching what main.py stores.

    In main.py the payload passed to vector_store.insert() looks like:
        {
            "description": "<text content>",   # text_field (top-level, not nested)
            "hash":        "<md5>",
            "created_at":  "<iso timestamp>",
            "user_id":     "<user>",
            ...any other caller-supplied metadata fields...
        }
    All fields are stored flat on the item — there is no nested "metadata" sub-key.
    """
    payload = {
        Constants.DESCRIPTION: description,
        "hash": hash_val,
        "created_at": created_at,
        "user_id": user_id,
    }
    payload.update(extra)
    return payload


@pytest.fixture
@patch("mem0.vector_stores.azure_cosmos_db_no_sql.CosmosClient")
def cosmos_db_client_fixture(mock_cosmos_client):
    # Demonstrate the recommended usage: pass user_agent_suffix=Constants.USER_AGENT
    # when constructing CosmosClient so requests are identifiable in diagnostics.
    mock_cosmos_client(
        url="https://test.documents.azure.com:443/",
        credential="fake-key",
        user_agent_suffix=Constants.USER_AGENT,
    )
    mock_client = mock_cosmos_client.return_value
    mock_db = mock_client.create_database_if_not_exists.return_value
    mock_collection = mock_db.create_container_if_not_exists.return_value

    azure_cosmos_db_nosql_vector = AzureCosmosDBNoSql(
        cosmos_client=mock_client,
        indexing_policy=get_vector_indexing_policy("flat"),
        cosmos_database_properties={},
        cosmos_collection_properties={Constants.PARTITION_KEY: PARTITION_KEY_VALUE},
        vector_properties=get_vector_properties("/vector", "float32", VECTOR_DIMENSION, "cosine"),
        vector_search_fields=get_vector_search_fields(
            text_field=Constants.DESCRIPTION, vector_field=Constants.VECTOR
        ),
        database_name=DATABASE_NAME,
        collection_name=COLLECTION_NAME,
        search_type=Constants.HYBRID,
        full_text_policy=get_full_text_policy(),
        full_text_search_enabled=True,
    )

    # `create_database_if_not_exists` lives on the CosmosClient, not on the
    # database proxy. Reset on the correct mock and use the idiomatic API.
    mock_client.create_database_if_not_exists.reset_mock()
    mock_db.create_container_if_not_exists.reset_mock()

    return azure_cosmos_db_nosql_vector, mock_collection, mock_db, mock_cosmos_client


def test_initialize_create_col(cosmos_db_client_fixture):
    cosmos_db_vector, mock_collection, mock_db, mock_cosmos_client = cosmos_db_client_fixture

    collection_name = cosmos_db_vector._collection_name
    vector_properties = cosmos_db_vector._vector_properties

    path = vector_properties["path"]
    data_type = vector_properties["dataType"]
    dimensions = vector_properties["dimensions"]
    distance_function = vector_properties["distanceFunction"]
    expected_vector_embedding_policy = get_vector_embedding_policy(
        path=path,
        data_type=data_type,
        dimensions=dimensions,
        distance_function=distance_function,
    )

    created_collection = cosmos_db_vector.create_col(
        name=collection_name,
        vector_size=dimensions,
        distance=distance_function,
    )

    assert created_collection == mock_collection
    mock_db.create_container_if_not_exists.assert_called_once_with(
        id=collection_name,
        partition_key=cosmos_db_vector._cosmos_collection_properties[Constants.PARTITION_KEY],
        indexing_policy=cosmos_db_vector._indexing_policy,
        default_ttl=cosmos_db_vector._cosmos_collection_properties.get(Constants.DEFAULT_TTL),
        offer_throughput=cosmos_db_vector._cosmos_collection_properties.get(Constants.OFFER_THROUGHPUT),
        unique_key_policy=cosmos_db_vector._cosmos_collection_properties.get(Constants.UNIQUE_KEY_POLICY),
        conflict_resolution_policy=cosmos_db_vector._cosmos_collection_properties.get(Constants.CONFLICT_RESOLUTION_POLICY),
        analytical_storage_ttl=cosmos_db_vector._cosmos_collection_properties.get(Constants.ANALYTICAL_STORAGE_TTL),
        computed_properties=cosmos_db_vector._cosmos_collection_properties.get(Constants.COMPUTED_PROPERTIES),
        etag=cosmos_db_vector._cosmos_collection_properties.get(Constants.ETAG),
        match_condition=cosmos_db_vector._cosmos_collection_properties.get(Constants.MATCH_CONDITION),
        session_token=cosmos_db_vector._cosmos_collection_properties.get(Constants.SESSION_TOKEN),
        initial_headers=cosmos_db_vector._cosmos_collection_properties.get(Constants.INITIAL_HEADERS),
        vector_embedding_policy=expected_vector_embedding_policy,
        full_text_policy=cosmos_db_vector._full_text_policy,
    )


def test_cosmos_client_user_agent():
    """Constants.USER_AGENT exists and is a non-empty string identifying mem0 requests."""
    assert isinstance(Constants.USER_AGENT, str)
    assert len(Constants.USER_AGENT) > 0
    assert "Mem0" in Constants.USER_AGENT


def test_validate_collection_exists(cosmos_db_client_fixture):
    cosmos_db_vector, mock_collection, mock_db, mock_cosmos_client = cosmos_db_client_fixture

    # check if validation fails when database does not exist
    expected_error_msg = "Database must be initialized before creating a collection."
    original_database = cosmos_db_vector._database
    with pytest.raises(ValueError, match=expected_error_msg):
        cosmos_db_vector._database = None
        cosmos_db_vector._validate_create_collection()
    cosmos_db_vector._database = original_database

    # check if validation fails when collection_name is None or empty
    expected_error_msg = "Collection name cannot be null or empty."
    original_collection_name = cosmos_db_vector._collection_name
    with pytest.raises(ValueError, match=expected_error_msg):
        cosmos_db_vector._collection_name = None
        cosmos_db_vector._validate_create_collection()
    with pytest.raises(ValueError, match=expected_error_msg):
        cosmos_db_vector._collection_name = ""
        cosmos_db_vector._validate_create_collection()
    cosmos_db_vector._collection_name = original_collection_name

    # check if validation fails when cosmos_collection_properties does not contain partition key
    expected_error_msg = r"'cosmos_collection_properties\[\"partition_key\"\]' is required and cannot be None when creating a collection\."
    original_cosmos_container_properties = cosmos_db_vector._cosmos_collection_properties
    with pytest.raises(ValueError, match=expected_error_msg):
        cosmos_db_vector._cosmos_collection_properties = {Constants.PARTITION_KEY: None}
        cosmos_db_vector._validate_create_collection()
    cosmos_db_vector._cosmos_collection_properties = original_cosmos_container_properties


def test_insert(cosmos_db_client_fixture):
    cosmos_db_vector, mock_collection, mock_db, mock_cosmos_client = cosmos_db_client_fixture

    vectors = [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]
    # Realistic mem0-style flat payloads: all fields are top-level, no nested "metadata" key.
    payloads = [
        make_mem0_payload(
            description="Border Collies are intelligent, ",
            user_id="alice",
            hash_val="abc123",
            created_at="2026-01-01T00:00:00",
        ),
        make_mem0_payload(
            description="energetic herders skilled in outdoor activities.",
            user_id="bob",
            hash_val="def456",
            created_at="2026-01-02T00:00:00",
        ),
    ]
    ids = ["vec1", "vec2"]

    cosmos_db_vector.insert(vectors=vectors, payloads=payloads, ids=ids)

    assert mock_collection.create_item.call_count == 2
    mock_collection.create_item.assert_any_call({
        "id": "vec1",
        Constants.DESCRIPTION: "Border Collies are intelligent, ",
        Constants.VECTOR: [0.1, 0.2, 0.3],
        "hash": "abc123",
        "created_at": "2026-01-01T00:00:00",
        "user_id": "alice",
    })
    mock_collection.create_item.assert_any_call({
        "id": "vec2",
        Constants.DESCRIPTION: "energetic herders skilled in outdoor activities.",
        Constants.VECTOR: [0.4, 0.5, 0.6],
        "hash": "def456",
        "created_at": "2026-01-02T00:00:00",
        "user_id": "bob",
    })

def test_insert_invalid_inputs(cosmos_db_client_fixture):
    cosmos_db_vector, mock_collection, mock_db, mock_cosmos_client = cosmos_db_client_fixture

    vector = [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]
    payloads = [
        {
            Constants.DESCRIPTION: "Border Collies are intelligent, ",
        },
        {
            Constants.DESCRIPTION: "energetic herders skilled in outdoor activities.",
        },
    ]
    ids = ["vec1"]

    # Test mismatched lengths
    error_message = "Length of vectors and payloads must match."
    with pytest.raises(ValueError, match=error_message):
        cosmos_db_vector.insert(vectors=[], payloads=payloads, ids=ids)

    error_message = "Length of ids must match vectors length."
    with pytest.raises(ValueError, match=error_message):
        cosmos_db_vector.insert(vectors=vector, payloads=payloads, ids=ids)


def test_search_vector(cosmos_db_client_fixture):
    cosmos_db_vector, mock_collection, mock_db, mock_cosmos_client = cosmos_db_client_fixture

    # Vector search
    for kwargs, query, parameters, query_item, output_data in get_vector_search_queries_and_parameters():
        mock_collection.query_items.return_value = query_item

        actual_output_data = cosmos_db_vector.search(**kwargs)
        mock_collection.query_items.assert_called_with(
            query=query,
            parameters=parameters,
            enable_cross_partition_query=True,
        )
        assert actual_output_data == output_data


def test_search_full_text(cosmos_db_client_fixture):
    cosmos_db_vector, mock_collection, mock_db, mock_cosmos_client = cosmos_db_client_fixture

    for kwargs, query, parameters, query_item, output_data in get_full_text_search_queries_and_parameters():
        mock_collection.query_items.return_value = query_item

        actual_output_data = cosmos_db_vector.search(**kwargs)
        mock_collection.query_items.assert_called_with(
            query=query,
            parameters=parameters,
            enable_cross_partition_query=True,
        )
        assert actual_output_data == output_data


def test_search_hybrid(cosmos_db_client_fixture):
    cosmos_db_vector, mock_collection, mock_db, mock_cosmos_client = cosmos_db_client_fixture

    for kwargs, query, parameters, query_item, output_data in get_hybrid_search_queries_and_parameters():
        mock_collection.query_items.return_value = query_item

        actual_output_data = cosmos_db_vector.search(**kwargs)
        mock_collection.query_items.assert_called_with(
            query=query,
            parameters=parameters,
            enable_cross_partition_query=True,
        )
        assert actual_output_data == output_data


def test_search_with_filters(cosmos_db_client_fixture):
    """Test that filters dict, raw where, and both combined all produce correct SQL queries."""
    cosmos_db_vector, mock_collection, mock_db, mock_cosmos_client = cosmos_db_client_fixture

    for kwargs, query, parameters, query_item, output_data in get_filter_search_queries_and_parameters():
        mock_collection.query_items.return_value = query_item

        actual_output_data = cosmos_db_vector.search(**kwargs)
        mock_collection.query_items.assert_called_with(
            query=query,
            parameters=parameters,
            enable_cross_partition_query=True,
        )
        assert actual_output_data == output_data


def test_score_threshold_boundary(cosmos_db_client_fixture):
    """Items with score exactly equal to threshold are included (>= not >)."""
    cosmos_db_vector, mock_collection, mock_db, mock_cosmos_client = cosmos_db_client_fixture

    threshold = 0.5
    query_items = [
        {'id': 'vec1', 'SimilarityScore': threshold, 'description': 'At threshold.', 'hash': 'h1'},
        {'id': 'vec2', 'SimilarityScore': 0.4, 'description': 'Below threshold.', 'hash': 'h2'},
    ]
    mock_collection.query_items.return_value = query_items

    results = cosmos_db_vector.search(
        search_type=Constants.VECTOR_SCORE_THRESHOLD,
        vectors=[0.1, 0.2, 0.3],
        limit=5,
        threshold=threshold,
    )

    # vec1 (score == threshold) must be included; vec2 (score < threshold) must not
    assert len(results) == 1
    assert results[0].id == 'vec1'


# ---------------------------------------------------------------------------
# Distance-function semantics for VectorDistance score thresholds.
#
# Per https://learn.microsoft.com/azure/cosmos-db/vector-search :
#   - cosine     : -1 (least similar)  ..  +1 (most similar)   higher = better
#   - dotproduct : -inf (least similar) .. +inf (most similar) higher = better
#   - euclidean  :  0  (most similar)  .. +inf (least similar) LOWER  = better
#
# The threshold filter must invert its comparison for euclidean, otherwise a
# perfect match (distance 0) is filtered out and a terrible match (large
# distance) is kept.
# ---------------------------------------------------------------------------


def _build_store_with_distance(cosmos_db_client_fixture, distance_function: str):
    """Return the fixture's store mutated to use the given distance function."""
    store, mock_collection, _, _ = cosmos_db_client_fixture
    store._vector_properties[Constants.DISTANCE_FUNCTION] = distance_function
    return store, mock_collection


@pytest.mark.parametrize("distance_function", ["cosine", "Cosine", "dotproduct", "DotProduct"])
def test_threshold_higher_is_better_metrics(cosmos_db_client_fixture, distance_function):
    """For cosine and dotproduct, score >= threshold is kept (higher = more similar)."""
    store, mock_collection = _build_store_with_distance(cosmos_db_client_fixture, distance_function)

    threshold = 0.5
    mock_collection.query_items.return_value = [
        {"id": "above", "SimilarityScore": 0.9, "description": "above", "hash": "h1"},
        {"id": "equal", "SimilarityScore": 0.5, "description": "equal", "hash": "h2"},
        {"id": "below", "SimilarityScore": 0.1, "description": "below", "hash": "h3"},
    ]

    results = store.search(
        search_type=Constants.VECTOR_SCORE_THRESHOLD,
        vectors=[0.1] * VECTOR_DIMENSION,
        limit=10,
        threshold=threshold,
    )

    kept_ids = {r.id for r in results}
    assert kept_ids == {"above", "equal"}


@pytest.mark.parametrize("distance_function", ["euclidean", "Euclidean", "EUCLIDEAN"])
def test_threshold_lower_is_better_for_euclidean(cosmos_db_client_fixture, distance_function):
    """For euclidean, score <= threshold is kept (lower distance = more similar).

    This is the regression test for the Cosmos-DB-specific bug where a perfect
    match (distance 0) was being filtered out as "below" the similarity
    threshold. See ``_passes_score_threshold`` in the adapter for context.
    """
    store, mock_collection = _build_store_with_distance(cosmos_db_client_fixture, distance_function)

    threshold = 0.5
    mock_collection.query_items.return_value = [
        {"id": "perfect", "SimilarityScore": 0.0, "description": "perfect", "hash": "h1"},
        {"id": "near", "SimilarityScore": 0.5, "description": "near", "hash": "h2"},
        {"id": "far", "SimilarityScore": 1.5, "description": "far", "hash": "h3"},
    ]

    results = store.search(
        search_type=Constants.VECTOR_SCORE_THRESHOLD,
        vectors=[0.1] * VECTOR_DIMENSION,
        limit=10,
        threshold=threshold,
    )

    kept_ids = {r.id for r in results}
    # Perfect (0) and near (0.5) are within the radius; far (1.5) is not.
    assert kept_ids == {"perfect", "near"}


def test_threshold_default_metric_is_cosine(cosmos_db_client_fixture):
    """If distanceFunction is unset, fall back to cosine semantics (higher = better)."""
    store, mock_collection, _, _ = cosmos_db_client_fixture
    store._vector_properties.pop(Constants.DISTANCE_FUNCTION, None)

    mock_collection.query_items.return_value = [
        {"id": "high", "SimilarityScore": 0.9, "description": "high", "hash": "h1"},
        {"id": "low", "SimilarityScore": 0.1, "description": "low", "hash": "h2"},
    ]

    results = store.search(
        search_type=Constants.VECTOR_SCORE_THRESHOLD,
        vectors=[0.1] * VECTOR_DIMENSION,
        limit=10,
        threshold=0.5,
    )
    assert {r.id for r in results} == {"high"}


def test_threshold_applies_to_hybrid_score_threshold_with_euclidean(cosmos_db_client_fixture):
    """HYBRID_SCORE_THRESHOLD also routes through the metric-aware filter."""
    store, mock_collection = _build_store_with_distance(cosmos_db_client_fixture, "euclidean")

    mock_collection.query_items.return_value = [
        {"id": "near", "SimilarityScore": 0.2, "description": "near", "hash": "h1"},
        {"id": "far", "SimilarityScore": 5.0, "description": "far", "hash": "h2"},
    ]

    results = store.search(
        search_type=Constants.HYBRID_SCORE_THRESHOLD,
        query="hello",
        vectors=[0.1] * VECTOR_DIMENSION,
        limit=10,
        threshold=1.0,
    )
    assert {r.id for r in results} == {"near"}


def test_threshold_zero_is_respected_for_euclidean(cosmos_db_client_fixture):
    """threshold=0 with euclidean must keep only exact matches, not be coerced."""
    store, mock_collection = _build_store_with_distance(cosmos_db_client_fixture, "euclidean")

    mock_collection.query_items.return_value = [
        {"id": "exact", "SimilarityScore": 0.0, "description": "exact", "hash": "h1"},
        {"id": "close", "SimilarityScore": 0.001, "description": "close", "hash": "h2"},
    ]

    results = store.search(
        search_type=Constants.VECTOR_SCORE_THRESHOLD,
        vectors=[0.1] * VECTOR_DIMENSION,
        limit=10,
        threshold=0.0,
    )
    assert {r.id for r in results} == {"exact"}


@pytest.mark.parametrize(
    "distance_function,score,threshold,expected",
    [
        ("cosine", 0.9, 0.5, True),
        ("cosine", 0.5, 0.5, True),
        ("cosine", 0.4, 0.5, False),
        ("cosine", -0.1, 0.0, False),
        ("dotproduct", 100.0, 1.0, True),
        ("dotproduct", -1.0, 0.0, False),
        ("euclidean", 0.0, 0.5, True),
        ("euclidean", 0.5, 0.5, True),
        ("euclidean", 0.51, 0.5, False),
        ("euclidean", 100.0, 0.5, False),
    ],
)
def test_passes_score_threshold_unit(
    cosmos_db_client_fixture, distance_function, score, threshold, expected
):
    """Unit test the metric-aware comparison helper directly."""
    store, _ = _build_store_with_distance(cosmos_db_client_fixture, distance_function)
    assert store._passes_score_threshold(score=score, threshold=threshold) is expected


def test_search_with_errors(cosmos_db_client_fixture):
    cosmos_db_vector, mock_collection, mock_db, mock_cosmos_client = cosmos_db_client_fixture

    # Test invalid search type
    error_message = r"Invalid search_type 'invalid_type'. Valid options are: vector, vector_score_threshold, full_text_search, full_text_ranking, hybrid, hybrid_score_threshold."
    with pytest.raises(ValueError, match=error_message):
        cosmos_db_vector.search(
            search_type="invalid_type",
            vectors=[0.1, 0.2, 0.3],
        )

    # Test missing vector for Vector Search
    search_type = Constants.VECTOR
    error_message = f"Embedding must be provided for search_type '{search_type}'."
    with pytest.raises(ValueError, match=error_message):
        cosmos_db_vector.search(search_type=search_type)

    # Test for `return_with_vectors` without vector
    error_message = "'return_with_vectors' can only be True for vector or hybrid search types"
    with pytest.raises(ValueError, match=error_message):
        cosmos_db_vector.search(
            search_type=Constants.FULL_TEXT_SEARCH,
            return_with_vectors=True,
        )

    # Test missing full_text_rank_filter for Full Text Ranking (no query to auto-build from)
    search_type = Constants.FULL_TEXT_RANKING
    error_message = "'full_text_rank_filter' is required for search_type"
    with pytest.raises(ValueError, match=error_message):
        cosmos_db_vector.search(search_type=search_type)


def test_delete(cosmos_db_client_fixture):
    cosmos_db_vector, mock_collection, mock_db, mock_cosmos_client = cosmos_db_client_fixture

    vector_id = "vec1"
    cosmos_db_vector.delete(vector_id=vector_id, partition_key_value=vector_id)

    mock_collection.delete_item.assert_called_once_with(
        item=vector_id,
        partition_key=vector_id
    )

def test_delete_cosmos_resource_not_found(cosmos_db_client_fixture):
    """delete() is idempotent: a missing item is treated as a no-op (matches Qdrant/Pinecone)."""
    cosmos_db_vector, mock_collection, mock_db, mock_cosmos_client = cosmos_db_client_fixture
    from mem0.vector_stores.azure_cosmos_db_no_sql import CosmosResourceNotFoundError
    vector_id = "vec_not_found"
    mock_collection.delete_item.side_effect = CosmosResourceNotFoundError(404, "Not found")
    # Should not raise — the higher-level delete_all() flow depends on this.
    cosmos_db_vector.delete(vector_id=vector_id, partition_key_value=vector_id)
    mock_collection.delete_item.assert_called_once_with(
        item=vector_id,
        partition_key=vector_id,
    )


def test_update(cosmos_db_client_fixture):
    cosmos_db_vector, mock_collection, mock_db, mock_cosmos_client = cosmos_db_client_fixture
    vector_id = "id1"
    updated_vector = [0.3] * VECTOR_DIMENSION
    updated_payload = make_mem0_payload(
        description="Updated: Border Collies are intelligent herders.",
        user_id="alice",
        hash_val="newHash",
        created_at="2026-03-01T00:00:00",
    )
    # read_item returns some existing item; update() is called with an explicit
    # payload so the existing item is not used for merging — only vector/payload
    # passed directly are written.
    mock_collection.read_item.return_value = {"id": vector_id, "vector": [0.1] * VECTOR_DIMENSION}
    mock_collection.upsert_item.return_value = MagicMock(matched_count=1)

    cosmos_db_vector.update(
        vector_id=vector_id,
        partition_key_value=vector_id,
        vector=updated_vector,
        payload=updated_payload,
    )

    expected_item = cosmos_db_vector._create_item_to_insert(
        vector=updated_vector,
        payload=updated_payload,
        id=vector_id,
    )
    mock_collection.upsert_item.assert_called_once_with(body=expected_item)


def test_update_preserves_extra_fields(cosmos_db_client_fixture):
    """Partial update (no payload supplied) must preserve all non-system fields
    from the existing item. With a realistic mem0 flat payload the preserved
    fields include description, hash, created_at, user_id, and any extras."""
    cosmos_db_vector, mock_collection, mock_db, mock_cosmos_client = cosmos_db_client_fixture

    vector_id = "id1"
    vector_key = cosmos_db_vector._vector_key
    existing_vector = [0.1] * VECTOR_DIMENSION
    # Simulate the full item as stored in Cosmos DB (flat payload + system fields)
    existing_item = {
        "id": vector_id,
        Constants.DESCRIPTION: "I love sci-fi movies.",
        "hash": "abc123",
        "created_at": "2026-01-01T00:00:00",
        "user_id": "alice",
        "agent_id": "agent-42",           # extra caller-supplied field
        vector_key: existing_vector,
        "_rid": "sys1", "_self": "sys2", "_etag": "sys3",
        "_attachments": "sys4", "_ts": 12345,
    }
    mock_collection.read_item.return_value = existing_item
    mock_collection.upsert_item.return_value = MagicMock()

    new_vector = [0.9] * VECTOR_DIMENSION
    cosmos_db_vector.update(vector_id=vector_id, vector=new_vector)

    expected_payload = {k: v for k, v in existing_item.items() if k not in cosmos_db_vector._excluded_payload_fields}
    expected_item = cosmos_db_vector._create_item_to_insert(
        vector=new_vector,
        payload=expected_payload,
        id=vector_id,
    )
    mock_collection.upsert_item.assert_called_once_with(body=expected_item)
    # All application-level flat fields must survive
    assert expected_item[Constants.DESCRIPTION] == "I love sci-fi movies."
    assert expected_item["hash"] == "abc123"
    assert expected_item["user_id"] == "alice"
    assert expected_item["agent_id"] == "agent-42"
    assert expected_item[vector_key] == new_vector


def test_get(cosmos_db_client_fixture):
    cosmos_db_vector, mock_collection, mock_db, mock_cosmos_client = cosmos_db_client_fixture

    vector_id = "id1"
    vector = [0.3] * VECTOR_DIMENSION
    vector_key = cosmos_db_vector._vector_key
    # Realistic flat mem0-style payload — no nested "metadata" sub-key
    payload = make_mem0_payload(
        description="I love sci-fi movies.",
        user_id="alice",
        hash_val="abc123",
        created_at="2026-01-01T00:00:00",
    )
    created_item = cosmos_db_vector._create_item_to_insert(
        vector=vector,
        payload=payload,
        id=vector_id,
    )

    mock_collection.read_item.return_value = created_item

    result = cosmos_db_vector.get(vector_id=vector_id, partition_key_value=vector_id)

    # Expected payload: all fields except those surfaced separately on OutputData
    # and the vector key (re-added below because return_with_vectors defaults to True).
    expected_payload = {k: v for k, v in created_item.items() if k not in cosmos_db_vector._excluded_payload_fields}
    expected_payload[vector_key] = vector

    assert result.id == vector_id
    assert result.score == 0.0
    assert result.payload == expected_payload
    assert result.payload[Constants.DESCRIPTION] == "I love sci-fi movies."
    assert result.payload["user_id"] == "alice"
    assert result.payload["hash"] == "abc123"
    mock_collection.read_item.assert_called_once_with(
        item=vector_id,
        partition_key=vector_id,
    )


def test_get_not_found_returns_none(cosmos_db_client_fixture):
    """get() returns None when the item does not exist (CosmosResourceNotFoundError)."""
    from mem0.vector_stores.azure_cosmos_db_no_sql import CosmosResourceNotFoundError

    cosmos_db_vector, mock_collection, mock_db, mock_cosmos_client = cosmos_db_client_fixture

    mock_collection.read_item.side_effect = CosmosResourceNotFoundError(404, "Not found")

    result = cosmos_db_vector.get(vector_id="missing-id", partition_key_value="missing-id")

    assert result is None
    mock_collection.read_item.assert_called_once_with(item="missing-id", partition_key="missing-id")


def test_list_cols(cosmos_db_client_fixture):
    """list_cols() returns the names of all containers in the database."""
    cosmos_db_vector, mock_collection, mock_db, mock_cosmos_client = cosmos_db_client_fixture

    mock_db.list_containers.return_value = [
        {"id": "collection1"},
        {"id": "collection2"},
    ]

    collections = cosmos_db_vector.list_cols()

    assert collections == ["collection1", "collection2"]
    mock_db.list_containers.assert_called_once()


def test_delete_col(cosmos_db_client_fixture):
    cosmos_db_vector, mock_collection, mock_db, mock_cosmos_client = cosmos_db_client_fixture

    cosmos_db_vector.delete_col()

    mock_db.delete_container.assert_called_once_with(
        container=cosmos_db_vector._collection_name
    )


def test_col_info(cosmos_db_client_fixture):
    cosmos_db_vector, mock_collection, mock_db, mock_cosmos_client = cosmos_db_client_fixture
    indexing_policy = get_vector_indexing_policy("flat")
    partition_key = {"paths": [f"/{Constants.PARTITION_KEY}"], "kind": "Hash"}

    mock_collection.read.return_value = {
        "id": COLLECTION_NAME,
        "indexingPolicy": indexing_policy,
        "partitionKey": partition_key,
    }

    info = cosmos_db_vector.col_info()

    assert info["id"] == COLLECTION_NAME
    assert info["indexingPolicy"] == indexing_policy
    assert info["partitionKey"] == partition_key
    mock_collection.read.assert_called_once()


def test_list(cosmos_db_client_fixture):
    cosmos_db_vector, mock_collection, mock_db, mock_cosmos_client = cosmos_db_client_fixture

    mock_collection.query_items.return_value = get_list_return_values()

    # Test without filters and limit — list() returns (records, None) tuple
    results, offset = cosmos_db_vector.list()
    assert offset is None
    assert len(results) == 2
    assert results[0].id == "vec1"
    assert results[1].id == "vec2"
    mock_collection.query_items.assert_called_once()
    expected_query = "SELECT TOP @limit * FROM c"
    expected_parameters = [
        {"name": "@limit", "value": 100},
    ]
    mock_collection.query_items.assert_called_with(
        query=expected_query,
        parameters=expected_parameters,
        enable_cross_partition_query=True,
    )

    # Test with filters and limit
    filters = {"metadata.a": 1, "id": "vec3"}
    limit = 2
    expected_query = "SELECT TOP @limit * FROM c WHERE c.metadata.a=@filter_value_0 AND c.id=@filter_value_1"
    expected_parameters = [
        {"name": "@limit", "value": limit},
        {"name": "@filter_value_0", "value": 1},
        {"name": "@filter_value_1", "value": "vec3"},
    ]
    cosmos_db_vector.list(filters=filters, limit=limit)
    mock_collection.query_items.assert_called_with(
        query=expected_query,
        parameters=expected_parameters,
        enable_cross_partition_query=True,
    )


def test_reset(cosmos_db_client_fixture):
    cosmos_db_vector, mock_collection, mock_db, mock_cosmos_client = cosmos_db_client_fixture

    new_collection = MagicMock()
    mock_db.create_container_if_not_exists.return_value = new_collection

    cosmos_db_vector.reset()

    mock_db.delete_container.assert_called_once_with(
        container=cosmos_db_vector._collection_name
    )
    mock_db.create_container_if_not_exists.assert_called_once()
    # reset() must update self._collection to the newly created container
    assert cosmos_db_vector._collection is new_collection


def test_vector_search_fields_none_raises_value_error():
    """Test that ValueError is raised if vector_search_fields is None in AzureCosmosDBNoSql."""
    with pytest.raises(ValueError, match="'vector_search_fields' is required and cannot be empty"):
        AzureCosmosDBNoSql(
            cosmos_client=MagicMock(),
            vector_properties={
                "path": "/vector", "dataType": "float32",
                "dimensions": 10, "distanceFunction": "cosine",
            },
            cosmos_collection_properties={"partition_key": "pk"},
            vector_search_fields=None,
        )


# ---------------------------------------------------------------------------
# Init validation tests
# ---------------------------------------------------------------------------

def _base_init_kwargs() -> dict:
    """Minimal valid kwargs for AzureCosmosDBNoSql.__init__ (except the field under test)."""
    return dict(
        cosmos_client=MagicMock(),
        vector_properties={"path": "/v", "dataType": "float32", "dimensions": 10, "distanceFunction": "cosine"},
        vector_search_fields={"text_field": "description", "vector_field": "vector"},
        cosmos_collection_properties={"partition_key": "pk"},
    )


def test_init_validates_cosmos_client_none():
    """ValueError when cosmos_client is None."""
    kwargs = _base_init_kwargs()
    kwargs["cosmos_client"] = None
    with pytest.raises(ValueError, match="'cosmos_client' is required and cannot be None"):
        AzureCosmosDBNoSql(**kwargs)


def test_init_validates_vector_properties_empty():
    """ValueError when vector_properties is empty."""
    kwargs = _base_init_kwargs()
    kwargs["vector_properties"] = {}
    with pytest.raises(ValueError, match="'vector_properties' is required and cannot be empty"):
        AzureCosmosDBNoSql(**kwargs)


def test_init_validates_vector_properties_missing_keys():
    """ValueError when vector_properties is missing required keys."""
    kwargs = _base_init_kwargs()
    kwargs["vector_properties"] = {"path": "/v"}  # missing dataType, dimensions, distanceFunction
    with pytest.raises(ValueError, match="'vector_properties' is missing required key"):
        AzureCosmosDBNoSql(**kwargs)


def test_init_validates_vector_properties_invalid_dimensions():
    """ValueError when dimensions is not a positive integer."""
    kwargs = _base_init_kwargs()
    kwargs["vector_properties"] = {"path": "/v", "dataType": "float32", "dimensions": 0, "distanceFunction": "cosine"}
    with pytest.raises(ValueError, match=r"'vector_properties\[\"dimensions\"\]' must be a positive integer"):
        AzureCosmosDBNoSql(**kwargs)


def test_init_validates_invalid_search_type():
    """ValueError when the init-level search_type is invalid."""
    kwargs = _base_init_kwargs()
    kwargs["search_type"] = "bad_type"
    with pytest.raises(ValueError, match="Invalid 'search_type'"):
        AzureCosmosDBNoSql(**kwargs)


def test_init_validates_database_name_empty():
    """ValueError when database_name is empty."""
    kwargs = _base_init_kwargs()
    kwargs["database_name"] = ""
    with pytest.raises(ValueError, match="'database_name' is required and cannot be empty"):
        AzureCosmosDBNoSql(**kwargs)


def test_init_validates_collection_name_empty():
    """ValueError when collection_name is empty."""
    kwargs = _base_init_kwargs()
    kwargs["collection_name"] = "  "
    with pytest.raises(ValueError, match="'collection_name' is required and cannot be empty"):
        AzureCosmosDBNoSql(**kwargs)


def test_init_validates_metadata_key_empty():
    """ValueError when metadata_key is empty."""
    kwargs = _base_init_kwargs()
    kwargs["metadata_key"] = ""
    with pytest.raises(ValueError, match="'metadata_key' is required and cannot be empty"):
        AzureCosmosDBNoSql(**kwargs)


def test_init_validates_table_alias_empty():
    """ValueError when table_alias is empty."""
    kwargs = _base_init_kwargs()
    kwargs["table_alias"] = ""
    with pytest.raises(ValueError, match="'table_alias' is required and cannot be empty"):
        AzureCosmosDBNoSql(**kwargs)


def test_init_full_text_enabled_requires_full_text_search_type():
    """ValueError when full_text_search_enabled=True but search_type is not a full-text type."""
    kwargs = _base_init_kwargs()
    kwargs.update(
        search_type=Constants.VECTOR,
        full_text_search_enabled=True,
        full_text_policy=get_full_text_policy(),
        indexing_policy=get_vector_indexing_policy("flat"),
    )
    with pytest.raises(ValueError, match="'search_type' must be a full-text search type"):
        AzureCosmosDBNoSql(**kwargs)


def test_init_full_text_enabled_requires_full_text_policy():
    """ValueError when full_text_search_enabled=True but full_text_policy has no fullTextPaths."""
    kwargs = _base_init_kwargs()
    kwargs.update(
        search_type=Constants.HYBRID,
        full_text_search_enabled=True,
        full_text_policy={"fullTextPaths": []},   # empty paths
        indexing_policy=get_vector_indexing_policy("flat"),
    )
    with pytest.raises(ValueError, match="'full_text_policy'.*required"):
        AzureCosmosDBNoSql(**kwargs)


def test_init_full_text_enabled_requires_full_text_indexes():
    """ValueError when full_text_search_enabled=True but indexing_policy lacks fullTextIndexes."""
    kwargs = _base_init_kwargs()
    kwargs.update(
        search_type=Constants.HYBRID,
        full_text_search_enabled=True,
        full_text_policy=get_full_text_policy(),
        indexing_policy={},  # no fullTextIndexes
    )
    with pytest.raises(ValueError, match="'indexing_policy' must include 'fullTextIndexes'"):
        AzureCosmosDBNoSql(**kwargs)


# ---------------------------------------------------------------------------
# insert() edge-case tests
# ---------------------------------------------------------------------------

def test_insert_auto_generates_ids(cosmos_db_client_fixture):
    """insert() auto-generates UUIDs when ids is not provided."""
    import uuid
    cosmos_db_vector, mock_collection, mock_db, mock_cosmos_client = cosmos_db_client_fixture

    cosmos_db_vector.insert(vectors=[[0.1, 0.2]], payloads=[{"description": "test"}])

    assert mock_collection.create_item.call_count == 1
    call_body = mock_collection.create_item.call_args[0][0]
    assert "id" in call_body
    # Must be a valid UUID
    uuid.UUID(call_body["id"])


def test_insert_defaults_payload_to_empty_dicts(cosmos_db_client_fixture):
    """insert() uses empty dicts for payload when payloads=None."""
    cosmos_db_vector, mock_collection, mock_db, mock_cosmos_client = cosmos_db_client_fixture

    cosmos_db_vector.insert(vectors=[[0.1, 0.2]], ids=["vec1"])  # no payloads

    mock_collection.create_item.assert_called_once_with({
        "id": "vec1",
        Constants.VECTOR: [0.1, 0.2],
    })


# ---------------------------------------------------------------------------
# update() edge-case tests
# ---------------------------------------------------------------------------

def test_update_not_found_raises_value_error(cosmos_db_client_fixture):
    """update() raises ValueError when the item does not exist."""
    from mem0.vector_stores.azure_cosmos_db_no_sql import CosmosResourceNotFoundError

    cosmos_db_vector, mock_collection, mock_db, mock_cosmos_client = cosmos_db_client_fixture
    mock_collection.read_item.side_effect = CosmosResourceNotFoundError(404, "Not found")

    with pytest.raises(ValueError, match="Cannot update: item 'missing-id' not found"):
        cosmos_db_vector.update(vector_id="missing-id", vector=[0.1], payload={"x": 1})


# ---------------------------------------------------------------------------
# delete() edge-case tests
# ---------------------------------------------------------------------------

def test_delete_empty_vector_id_raises_value_error(cosmos_db_client_fixture):
    """delete() raises ValueError when vector_id is empty."""
    cosmos_db_vector, mock_collection, mock_db, mock_cosmos_client = cosmos_db_client_fixture

    with pytest.raises(ValueError, match="vector_id cannot be null or empty"):
        cosmos_db_vector.delete(vector_id="")


def test_delete_defaults_partition_key_to_vector_id(cosmos_db_client_fixture):
    """delete() uses vector_id as partition key when partition_key_value is not provided."""
    cosmos_db_vector, mock_collection, mock_db, mock_cosmos_client = cosmos_db_client_fixture

    cosmos_db_vector.delete(vector_id="vec1")  # no partition_key_value

    mock_collection.delete_item.assert_called_once_with(item="vec1", partition_key="vec1")


# ---------------------------------------------------------------------------
# Filter-key SQL-injection guard (search() and list())
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "bad_key",
    [
        "user_id OR 1=1 --",                # classic OR-injection chain
        "user_id; DROP TABLE c; --",        # stacked-statement attempt
        "user_id=@v0 OR 1=1",               # closes the equality early
        "metadata.user_id OR 1=1",          # nested key with OR-injection
        "metadata..user_id",                # malformed dotted chain
        ".user_id",                         # leading dot
        "user_id.",                         # trailing dot
        "1user_id",                         # leading digit (not an identifier)
        "user id",                          # whitespace inside
        "",                                 # empty key
    ],
)
def test_search_rejects_invalid_filter_keys(cosmos_db_client_fixture, bad_key):
    """Filter keys are interpolated into SQL — anything that is not a dot-separated
    identifier chain must be rejected so callers cannot smuggle SQL fragments."""
    cosmos_db_vector, mock_collection, mock_db, mock_cosmos_client = cosmos_db_client_fixture

    with pytest.raises(ValueError, match="Invalid filter key"):
        cosmos_db_vector.search(
            search_type=Constants.VECTOR,
            vectors=[0.1] * VECTOR_DIMENSION,
            filters={bad_key: "alice"},
        )
    # Query must never have been issued against the collection.
    mock_collection.query_items.assert_not_called()


def test_list_rejects_invalid_filter_keys(cosmos_db_client_fixture):
    """Same identifier-chain validation applies to list() filters."""
    cosmos_db_vector, mock_collection, mock_db, mock_cosmos_client = cosmos_db_client_fixture

    with pytest.raises(ValueError, match="Invalid filter key"):
        cosmos_db_vector.list(filters={"user_id OR 1=1 --": "alice"})
    mock_collection.query_items.assert_not_called()


@pytest.mark.parametrize(
    "good_key",
    ["user_id", "metadata", "metadata.user_id", "metadata.nested.field", "_underscored", "a1.b2"],
)
def test_search_accepts_valid_filter_keys(cosmos_db_client_fixture, good_key):
    """Sanity check: legitimate keys still pass through the validator."""
    cosmos_db_vector, mock_collection, mock_db, mock_cosmos_client = cosmos_db_client_fixture

    mock_collection.query_items.return_value = []
    # Should not raise.
    cosmos_db_vector.search(
        search_type=Constants.VECTOR,
        vectors=[0.1] * VECTOR_DIMENSION,
        filters={good_key: "alice"},
    )
    mock_collection.query_items.assert_called_once()


# ---------------------------------------------------------------------------
# Combined `filters` + raw `where`: the raw fragment must be parenthesized
# so a nested OR can never bind looser than the AND that joins it to the
# structured filters (otherwise rows could leak across tenants).
# ---------------------------------------------------------------------------

def test_search_parenthesizes_raw_where_when_combined_with_filters(cosmos_db_client_fixture):
    cosmos_db_vector, mock_collection, mock_db, mock_cosmos_client = cosmos_db_client_fixture
    mock_collection.query_items.return_value = []

    cosmos_db_vector.search(
        search_type=Constants.VECTOR,
        vectors=[0.1] * VECTOR_DIMENSION,
        filters={"user_id": "alice"},
        where="x=1 OR y=2",
        limit=5,
    )

    issued_query = mock_collection.query_items.call_args.kwargs["query"]
    assert "AND (x=1 OR y=2)" in issued_query, issued_query
    # Defense-in-depth: the unparenthesized form must NOT appear.
    assert "AND x=1 OR y=2" not in issued_query, issued_query


def test_search_parenthesizes_raw_where_alone(cosmos_db_client_fixture):
    cosmos_db_vector, mock_collection, mock_db, mock_cosmos_client = cosmos_db_client_fixture
    mock_collection.query_items.return_value = []

    cosmos_db_vector.search(
        search_type=Constants.VECTOR,
        vectors=[0.1] * VECTOR_DIMENSION,
        where="x=1 OR y=2",
        limit=5,
    )

    issued_query = mock_collection.query_items.call_args.kwargs["query"]
    assert "WHERE (x=1 OR y=2)" in issued_query, issued_query



# ---------------------------------------------------------------------------
# get() edge-case tests
# ---------------------------------------------------------------------------

def test_get_empty_vector_id_raises_value_error(cosmos_db_client_fixture):
    """get() raises ValueError when vector_id is empty."""
    cosmos_db_vector, mock_collection, mock_db, mock_cosmos_client = cosmos_db_client_fixture

    with pytest.raises(ValueError, match="vector_id cannot be null or empty"):
        cosmos_db_vector.get(vector_id="")


def test_get_default_partition_key(cosmos_db_client_fixture):
    """get() uses vector_id as partition key when partition_key_value is not provided."""
    cosmos_db_vector, mock_collection, mock_db, mock_cosmos_client = cosmos_db_client_fixture

    mock_collection.read_item.return_value = {"id": "vec1", Constants.VECTOR: [0.1]}

    cosmos_db_vector.get(vector_id="vec1")

    mock_collection.read_item.assert_called_once_with(item="vec1", partition_key="vec1")


def test_get_return_with_vectors_false(cosmos_db_client_fixture):
    """get() with return_with_vectors=False excludes the vector field from the payload."""
    cosmos_db_vector, mock_collection, mock_db, mock_cosmos_client = cosmos_db_client_fixture

    mock_collection.read_item.return_value = {
        "id": "vec1",
        Constants.DESCRIPTION: "hello world",
        Constants.VECTOR: [0.1, 0.2, 0.3],
    }

    result = cosmos_db_vector.get(vector_id="vec1", return_with_vectors=False)

    assert Constants.VECTOR not in result.payload
    assert result.payload[Constants.DESCRIPTION] == "hello world"


# ---------------------------------------------------------------------------
# _build_output_data_from_item — Cosmos internal fields stripped
# ---------------------------------------------------------------------------

def test_build_output_data_strips_cosmos_internal_fields(cosmos_db_client_fixture):
    """_build_output_data_from_item strips all five Cosmos DB system fields."""
    cosmos_db_vector, mock_collection, mock_db, mock_cosmos_client = cosmos_db_client_fixture

    item = {
        "id": "vec1",
        Constants.DESCRIPTION: "Test payload",
        "hash": "abc",
        Constants.VECTOR: [0.1],
        "_rid": "rid-val",
        "_self": "self-val",
        "_etag": '"etag-val"',
        "_attachments": "attachments/",
        "_ts": 1700000000,
    }

    result = cosmos_db_vector._build_output_data_from_item(item, return_with_vectors=False)

    # All Cosmos internal fields and id must be absent from payload
    for field in ("_rid", "_self", "_etag", "_attachments", "_ts", "id", Constants.VECTOR):
        assert field not in result.payload, f"field '{field}' should be stripped"
    assert result.id == "vec1"
    assert result.payload[Constants.DESCRIPTION] == "Test payload"
    assert result.payload["hash"] == "abc"


# ---------------------------------------------------------------------------
# search() — full_text_search_enabled=False raises error for full-text types
# ---------------------------------------------------------------------------

def test_search_full_text_disabled_raises_error():
    """search() raises ValueError for full-text search types when the store was configured
    with full_text_search_enabled=False."""
    mock_client = MagicMock()
    mock_client.create_database_if_not_exists.return_value = MagicMock()

    store = AzureCosmosDBNoSql(
        cosmos_client=mock_client,
        vector_properties={"path": "/v", "dataType": "float32", "dimensions": 10, "distanceFunction": "cosine"},
        vector_search_fields={"text_field": "description", "vector_field": "vector"},
        search_type=Constants.VECTOR,
        full_text_search_enabled=False,
        cosmos_collection_properties={"partition_key": "pk"},
    )

    for ft_type in (Constants.FULL_TEXT_SEARCH, Constants.FULL_TEXT_RANKING):
        with pytest.raises(ValueError, match="Full text search is not enabled"):
            store.search(search_type=ft_type, where="FullTextContains(c.description, 'test')")


# ---------------------------------------------------------------------------
# search() — HYBRID (no threshold) does not filter results by score
# ---------------------------------------------------------------------------

def test_search_hybrid_returns_all_items_regardless_of_score(cosmos_db_client_fixture):
    """HYBRID search (not HYBRID_SCORE_THRESHOLD) must not apply a threshold filter."""
    cosmos_db_vector, mock_collection, mock_db, mock_cosmos_client = cosmos_db_client_fixture

    query_items = [
        {"id": "vec1", "SimilarityScore": 0.01, "description": "very low score", "hash": "h1"},
        {"id": "vec2", "SimilarityScore": 0.99, "description": "high score", "hash": "h2"},
    ]
    mock_collection.query_items.return_value = query_items

    results = cosmos_db_vector.search(
        search_type=Constants.HYBRID,
        vectors=[0.1, 0.2, 0.3],
        full_text_rank_filter=[{"search_field": "description", "search_text": "low high"}],
        limit=5,
    )

    # All items returned — no score filtering for plain HYBRID
    assert len(results) == 2
    assert {r.id for r in results} == {"vec1", "vec2"}


# ---------------------------------------------------------------------------
# list() — vector field excluded from payload
# ---------------------------------------------------------------------------

def test_list_excludes_vectors_from_payload(cosmos_db_client_fixture):
    """list() returns items without vector embeddings in the payload."""
    cosmos_db_vector, mock_collection, mock_db, mock_cosmos_client = cosmos_db_client_fixture

    mock_collection.query_items.return_value = [
        {
            "id": "vec1",
            Constants.DESCRIPTION: "Border Collies are intelligent herders.",
            Constants.VECTOR: [0.1, 0.2, 0.3],
            "hash": "abc123",
        }
    ]

    results, _ = cosmos_db_vector.list(limit=1)

    assert len(results) == 1
    assert Constants.VECTOR not in results[0].payload
    assert results[0].payload[Constants.DESCRIPTION] == "Border Collies are intelligent herders."


def test_list_delete_all_compatible(cosmos_db_client_fixture):
    """list()[0] must return the record list so Memory.delete_all() works correctly."""
    cosmos_db_vector, mock_collection, mock_db, mock_cosmos_client = cosmos_db_client_fixture

    mock_collection.query_items.return_value = [
        {"id": "vec1", Constants.DESCRIPTION: "Test", "hash": "h1"},
        {"id": "vec2", Constants.DESCRIPTION: "Test2", "hash": "h2"},
    ]

    records = cosmos_db_vector.list()[0]  # Memory.delete_all() pattern

    assert len(records) == 2
    assert records[0].id == "vec1"
    assert records[1].id == "vec2"


def test_search_auto_builds_full_text_rank_filter_from_query(cosmos_db_client_fixture):
    """search() with a text-ranking type auto-builds full_text_rank_filter from query+text_field."""
    cosmos_db_vector, mock_collection, mock_db, mock_cosmos_client = cosmos_db_client_fixture

    mock_collection.query_items.return_value = [
        {"id": "vec1", "SimilarityScore": 0.8, "description": "I love sci-fi movies.", "hash": "h1"},
    ]

    # Call with query= and vectors= but no full_text_rank_filter — should auto-build
    results = cosmos_db_vector.search(
        query="sci-fi movies",
        vectors=[0.1, 0.2, 0.3],
        search_type=Constants.HYBRID,
        limit=5,
    )

    assert len(results) == 1
    # The SQL query must contain FullTextScore with the text_field ("description") and query terms
    call_kwargs = mock_collection.query_items.call_args[1]
    assert "FullTextScore" in call_kwargs["query"]
    assert "@description" in call_kwargs["query"]


def test_search_empty_search_text_raises_error(cosmos_db_client_fixture):
    """full_text_rank_filter with empty search_text raises ValueError before querying Cosmos DB."""
    cosmos_db_vector, mock_collection, mock_db, mock_cosmos_client = cosmos_db_client_fixture

    with pytest.raises(ValueError, match="'search_text'.*cannot be empty"):
        cosmos_db_vector.search(
            search_type=Constants.FULL_TEXT_RANKING,
            full_text_rank_filter=[{"search_field": "description", "search_text": "   "}],
            limit=5,
        )

def get_kwargs(
        search_type: str,
        vectors: Optional[List[float]] = None,
        limit: Optional[int] = None,
        filters: Optional[Dict[str, Any]] = None,
        return_with_vectors: Optional[bool] = None,
        full_text_rank_filter: Optional[List[Dict[str, str]]] = None,
        projection_mapping: Optional[Dict[str, str]] = None,
        offset_limit: Optional[str] = None,
        where: Optional[str] = None,
        weights: Optional[List[float]] = None,
) -> Dict[str, Any]:
    kwargs: Dict[str, Any] = {
        "search_type": search_type,
    }
    if vectors is not None:
        kwargs["vectors"] = vectors
    if limit is not None:
        kwargs["limit"] = limit
    if filters is not None:
        kwargs["filters"] = filters
    if return_with_vectors is not None:
        kwargs["return_with_vectors"] = return_with_vectors
    if full_text_rank_filter is not None:
        kwargs["full_text_rank_filter"] = full_text_rank_filter
    if projection_mapping is not None:
        kwargs["projection_mapping"] = projection_mapping
    if offset_limit is not None:
        kwargs["offset_limit"] = offset_limit
    if where is not None:
        kwargs["where"] = where
    if weights is not None:
        kwargs["weights"] = weights

    return kwargs

# Generate various vector search queries and their expected parameters
def get_vector_search_queries_and_parameters() -> List[Tuple[Dict[str, Any], str, List[Dict[str, Any]]]]:
    queries_and_parameters = []

    vectors = [0.1, 0.2, 0.3]
    limit = 2

    # Case 1: Simple Vector search with k
    expected_query = (
        "SELECT TOP @limit *, VectorDistance(c[@vectorKey], @vector) as SimilarityScore "
        "FROM c ORDER BY VectorDistance(c[@vectorKey], @vector)"
    )
    expected_parameters = [
        {"name": "@limit", "value": limit},
        {"name": "@vectorKey", "value": Constants.VECTOR},
        {"name": "@vector", "value": vectors},
    ]
    expected_query_items = [
        {
            'id': 'vec1',
            'SimilarityScore': 0.123,
            'description': 'I love sci-fi movies.',
            'hash': 'abc123',
            'created_at': '2026-01-01T00:00:00',
            'user_id': 'alice',
        },
        {
            'id': 'vec2',
            'SimilarityScore': 0.223,
            'description': 'I enjoy reading fantasy novels.',
            'hash': 'def456',
            'created_at': '2026-01-02T00:00:00',
            'user_id': 'bob',
        },
    ]
    expected_output_data = [
        OutputData(
            id='vec1', score=0.123,
            payload={
                'description': 'I love sci-fi movies.',
                'hash': 'abc123',
                'created_at': '2026-01-01T00:00:00',
                'user_id': 'alice',
            }
        ),
        OutputData(
            id='vec2', score=0.223,
            payload={
                'description': 'I enjoy reading fantasy novels.',
                'hash': 'def456',
                'created_at': '2026-01-02T00:00:00',
                'user_id': 'bob',
            }
        ),
    ]

    queries_and_parameters.append(
        (
            get_kwargs(
                search_type=Constants.VECTOR,
                vectors=vectors,
                limit=limit,
            ),
            expected_query,
            expected_parameters,
            expected_query_items,
            expected_output_data,
        )
    )

    # Case 2: with vector
    expected_query = (
        "SELECT TOP @limit *, VectorDistance(c[@vectorKey], @vector) as SimilarityScore "
        "FROM c ORDER BY VectorDistance(c[@vectorKey], @vector)"
    )
    expected_parameters = [
        {"name": "@limit", "value": limit},
        {"name": "@vectorKey", "value": Constants.VECTOR},
        {"name": "@vector", "value": vectors},
    ]
    expected_query_items = [
        {
            'id': 'vec1',
            'SimilarityScore': 0.123,
            'description': 'I love sci-fi movies.',
            'vector': [0.1, 0.2, 0.3],
            'hash': 'abc123',
            'created_at': '2026-01-01T00:00:00',
            'user_id': 'alice',
        },
        {
            'id': 'vec2',
            'SimilarityScore': 0.223,
            'description': 'I enjoy reading fantasy novels.',
            'vector': [0.2, 0.2, 0.3],
            'hash': 'def456',
            'created_at': '2026-01-02T00:00:00',
            'user_id': 'bob',
        },
    ]
    expected_output_data = [
        OutputData(
            id='vec1', score=0.123,
            payload={
                'description': 'I love sci-fi movies.',
                'vector': [0.1, 0.2, 0.3],
                'hash': 'abc123',
                'created_at': '2026-01-01T00:00:00',
                'user_id': 'alice',
            }
        ),
        OutputData(
            id='vec2', score=0.223,
            payload={
                'description': 'I enjoy reading fantasy novels.',
                'vector': [0.2, 0.2, 0.3],
                'hash': 'def456',
                'created_at': '2026-01-02T00:00:00',
                'user_id': 'bob',
            }
        ),
    ]

    queries_and_parameters.append(
        (
            get_kwargs(
                search_type=Constants.VECTOR,
                vectors=vectors,
                limit=limit,
                return_with_vectors=True,
            ),
            expected_query,
            expected_parameters,
            expected_query_items,
            expected_output_data,
        )
    )

    # Case 3: With projection mapping
    projection_mapping = {
        "id": "id",
        "description": "text",
    }
    expected_query = (
        "SELECT TOP @limit c.id as id, c.description as text, VectorDistance(c[@vectorKey], @vector) as SimilarityScore "
        "FROM c "
        "ORDER BY VectorDistance(c[@vectorKey], @vector)"
    )
    expected_parameters = [
        {"name": "@limit", "value": limit},
        {"name": "@vectorKey", "value": Constants.VECTOR},
        {"name": "@vector", "value": vectors},
    ]
    expected_query_items = [
        {
            'id': 'vec1',
            'SimilarityScore': 0.123,
            'text': 'Sample description for vector 1.',
            'metadata': {'a': 1, 'b': 2, 'c': 3}
        },
        {
            'id': 'vec2',
            'SimilarityScore': 0.223,
            'text': 'Sample description for vector 2.',
            'metadata': {'a': 2, 'b': 2, 'c': 3}
        }
    ]
    expected_output_data = [
        OutputData(
            id='vec1', score=0.123,
            payload={
                'id': 'vec1',
                'text': 'Sample description for vector 1.',
            }
        ),
        OutputData(
            id='vec2', score=0.223,
            payload={
                'id': 'vec2',
                'text': 'Sample description for vector 2.',
            }
        )
    ]
    queries_and_parameters.append(
        (
            get_kwargs(
                search_type=Constants.VECTOR,
                vectors=vectors,
                limit=limit,
                projection_mapping=projection_mapping
            ),
            expected_query,
            expected_parameters,
            expected_query_items,
            expected_output_data,
        )
    )


    # Case 4: With offset_limit
    off_set_limit = "OFFSET 5 LIMIT 1"
    expected_query = (
        "SELECT *, VectorDistance(c[@vectorKey], @vector) as SimilarityScore "
        "FROM c ORDER BY VectorDistance(c[@vectorKey], @vector) "
        f"{off_set_limit}"
    )
    expected_parameters = [
        {"name": "@vectorKey", "value": Constants.VECTOR},
        {"name": "@vector", "value": vectors},
    ]
    expected_query_items = [
        {
            'id': 'vec1',
            'SimilarityScore': 0.123,
            'description': 'I love sci-fi movies.',
            'hash': 'abc123',
            'created_at': '2026-01-01T00:00:00',
            'user_id': 'alice',
        }
    ]
    expected_output_data = [
        OutputData(
            id='vec1', score=0.123,
            payload={
                'description': 'I love sci-fi movies.',
                'hash': 'abc123',
                'created_at': '2026-01-01T00:00:00',
                'user_id': 'alice',
            }
        )
    ]
    queries_and_parameters.append(
        (
            get_kwargs(
                search_type=Constants.VECTOR,
                vectors=vectors,
                offset_limit=off_set_limit,
            ),
            expected_query,
            expected_parameters,
            expected_query_items,
            expected_output_data,
        )
    )

    # Case 5: With where filter (raw `where` is wrapped in parens to preserve precedence)
    where_filter = "c.user_id='alice'"
    expected_query = (
        "SELECT TOP @limit *, VectorDistance(c[@vectorKey], @vector) as SimilarityScore "
        "FROM c "
        "WHERE (c.user_id='alice') "
        "ORDER BY VectorDistance(c[@vectorKey], @vector)"
    )
    expected_parameters = [
        {"name": "@limit", "value": limit},
        {"name": "@vectorKey", "value": Constants.VECTOR},
        {"name": "@vector", "value": vectors},
    ]
    queries_and_parameters.append(
        (
            get_kwargs(
                search_type=Constants.VECTOR,
                vectors=vectors,
                where=where_filter,
                limit=limit,
            ),
            expected_query,
            expected_parameters,
            expected_query_items,
            expected_output_data,
        )
    )

    # Case 6: filters dict only (no raw where)
    filters = {"user_id": "alice", "hash": "abc123"}
    expected_query = (
        "SELECT TOP @limit *, VectorDistance(c[@vectorKey], @vector) as SimilarityScore "
        "FROM c "
        "WHERE c.user_id=@filter_value_0 AND c.hash=@filter_value_1 "
        "ORDER BY VectorDistance(c[@vectorKey], @vector)"
    )
    expected_parameters = [
        {"name": "@limit", "value": limit},
        {"name": "@vectorKey", "value": Constants.VECTOR},
        {"name": "@vector", "value": vectors},
        {"name": "@filter_value_0", "value": "alice"},
        {"name": "@filter_value_1", "value": "abc123"},
    ]
    queries_and_parameters.append(
        (
            get_kwargs(
                search_type=Constants.VECTOR,
                vectors=vectors,
                filters=filters,
                limit=limit,
            ),
            expected_query,
            expected_parameters,
            expected_query_items,
            expected_output_data,
        )
    )

    # Case 7: filters dict AND raw where combined with AND
    where_filter = "FullTextContains(c.description, 'sci-fi')"
    expected_query = (
        "SELECT TOP @limit *, VectorDistance(c[@vectorKey], @vector) as SimilarityScore "
        "FROM c "
        f"WHERE c.user_id=@filter_value_0 AND c.hash=@filter_value_1 AND ({where_filter}) "
        "ORDER BY VectorDistance(c[@vectorKey], @vector)"
    )
    expected_parameters = [
        {"name": "@limit", "value": limit},
        {"name": "@vectorKey", "value": Constants.VECTOR},
        {"name": "@vector", "value": vectors},
        {"name": "@filter_value_0", "value": "alice"},
        {"name": "@filter_value_1", "value": "abc123"},
    ]
    queries_and_parameters.append(
        (
            get_kwargs(
                search_type=Constants.VECTOR,
                vectors=vectors,
                filters=filters,
                where=where_filter,
                limit=limit,
            ),
            expected_query,
            expected_parameters,
            expected_query_items,
            expected_output_data,
        )
    )

    # Case 8: Vector score threshold — items below threshold are filtered out
    expected_query = (
        "SELECT TOP @limit *, VectorDistance(c[@vectorKey], @vector) as SimilarityScore "
        "FROM c ORDER BY VectorDistance(c[@vectorKey], @vector)"
    )
    expected_parameters = [
        {"name": "@limit", "value": limit},
        {"name": "@vectorKey", "value": Constants.VECTOR},
        {"name": "@vector", "value": vectors},
    ]
    expected_query_items = [
        {
            'id': 'vec1',
            'SimilarityScore': 0.123,
            'description': 'I love sci-fi movies.',
            'hash': 'abc123',
            'created_at': '2026-01-01T00:00:00',
            'user_id': 'alice',
        },
        {
            'id': 'vec2',
            'SimilarityScore': 0.623,
            'description': 'I enjoy reading fantasy novels.',
            'hash': 'def456',
            'created_at': '2026-01-02T00:00:00',
            'user_id': 'bob',
        },
    ]
    expected_output_data = [
        OutputData(
            id='vec2', score=0.623,
            payload={
                'description': 'I enjoy reading fantasy novels.',
                'hash': 'def456',
                'created_at': '2026-01-02T00:00:00',
                'user_id': 'bob',
            }
        )
    ]

    queries_and_parameters.append(
        (
            get_kwargs(
                search_type=Constants.VECTOR_SCORE_THRESHOLD,
                vectors=vectors,
                limit=limit,
            ),
            expected_query,
            expected_parameters,
            expected_query_items,
            expected_output_data,
        )
    )

    return queries_and_parameters

# generate various full text search queries and their expected parameters
def get_full_text_search_queries_and_parameters() -> List[Tuple[Dict[str, Any], str, List[Dict[str, Any]]]]:
    queries_and_parameters = []

    search_text = "intelligent herders"
    full_text_rank_filter = [{"search_field": "description", "search_text": search_text}]
    limit = 2

    # Case 1: Simple full text search (raw `where` is wrapped in parens to preserve precedence)
    where = "FullTextContainsAny(c.description, 'intelligent', 'herders')"
    expected_query = (
        "SELECT TOP @limit * "
        "FROM c "
        "WHERE (FullTextContainsAny(c.description, 'intelligent', 'herders'))"
    )
    expected_parameters = [
        {"name": "@limit", "value": limit},
    ]
    expected_query_items = [
        {
            'id': 'vec1',
            'description': 'I love sci-fi movies.',
            'hash': 'abc123',
            'created_at': '2026-01-01T00:00:00',
            'user_id': 'alice',
        },
        {
            'id': 'vec2',
            'description': 'I enjoy reading fantasy novels.',
            'hash': 'def456',
            'created_at': '2026-01-02T00:00:00',
            'user_id': 'bob',
        },
    ]
    expected_output_data = [
        OutputData(
            id='vec1', score=0.0,
            payload={
                'description': 'I love sci-fi movies.',
                'hash': 'abc123',
                'created_at': '2026-01-01T00:00:00',
                'user_id': 'alice',
            }
        ),
        OutputData(
            id='vec2', score=0.0,
            payload={
                'description': 'I enjoy reading fantasy novels.',
                'hash': 'def456',
                'created_at': '2026-01-02T00:00:00',
                'user_id': 'bob',
            }
        ),
    ]

    queries_and_parameters.append(
        (
            get_kwargs(
                search_type=Constants.FULL_TEXT_SEARCH,
                where=where,
                limit=limit,
            ),
            expected_query,
            expected_parameters,
            expected_query_items,
            expected_output_data,
        )
    )

    # Case 2: Simple full text ranking
    expected_query = (
        "SELECT TOP @limit * "
        "FROM c "
        "ORDER BY RANK FullTextScore(c[@description], @description_term_0, @description_term_1)"
    )
    expected_parameters = [
        {"name": "@limit", "value": limit},
        {"name": "@description", "value": "description"},
        {"name": "@description_term_0", "value": "intelligent"},
        {"name": "@description_term_1", "value": "herders"},
    ]
    # Full text ranking does not return SimilarityScore
    expected_query_items_ranking = [
        {
            'id': 'vec1',
            'description': 'I love sci-fi movies.',
            'hash': 'abc123',
            'created_at': '2026-01-01T00:00:00',
            'user_id': 'alice',
        },
        {
            'id': 'vec2',
            'description': 'I enjoy reading fantasy novels.',
            'hash': 'def456',
            'created_at': '2026-01-02T00:00:00',
            'user_id': 'bob',
        },
    ]

    queries_and_parameters.append(
        (
            get_kwargs(
                search_type=Constants.FULL_TEXT_RANKING,
                full_text_rank_filter=full_text_rank_filter,
                limit=limit,
            ),
            expected_query,
            expected_parameters,
            expected_query_items_ranking,
            expected_output_data,
        )
    )

    # Case 3: Full text ranking with multiple search fields
    full_text_rank_filter = [
        {"search_field": "description", "search_text": search_text},
        {"search_field": "metadata", "search_text": search_text}
    ]
    expected_query = (
        "SELECT TOP @limit * "
        "FROM c "
        "ORDER BY RANK RRF(FullTextScore(c[@description], @description_term_0, @description_term_1), FullTextScore(c[@metadata], @metadata_term_0, @metadata_term_1))"
    )
    expected_parameters = [
        {"name": "@limit", "value": limit},
        {"name": "@description", "value": "description"},
        {"name": "@description_term_0", "value": "intelligent"},
        {"name": "@description_term_1", "value": "herders"},
        {"name": "@metadata", "value": "metadata"},
        {"name": "@metadata_term_0", "value": "intelligent"},
        {"name": "@metadata_term_1", "value": "herders"},
    ]

    queries_and_parameters.append(
        (
            get_kwargs(
                search_type=Constants.FULL_TEXT_RANKING,
                full_text_rank_filter=full_text_rank_filter,
                limit=limit,
            ),
            expected_query,
            expected_parameters,
            expected_query_items_ranking,
            expected_output_data,
        )
    )

    return queries_and_parameters

def get_hybrid_search_queries_and_parameters() -> List[Tuple[Dict[str, Any], str, List[Dict[str, Any]]]]:
    queries_and_parameters = []

    vectors = [0.1, 0.2, 0.3]
    search_text = "intelligent herders"
    full_text_rank_filter = [{"search_field": "description", "search_text": search_text}]
    limit = 2

    # Case 1: Hybrid search with score threshold
    expected_query = (
        "SELECT TOP @limit *, VectorDistance(c[@vectorKey], @vector) as SimilarityScore "
        "FROM c "
        "ORDER BY RANK RRF(FullTextScore(c[@description], @description_term_0, @description_term_1), VectorDistance(c[@vectorKey], @vector))"
    )
    expected_parameters = [
        {"name": "@limit", "value": limit},
        {"name": "@vectorKey", "value": Constants.VECTOR},
        {"name": "@vector", "value": vectors},
        {"name": "@description", "value": Constants.DESCRIPTION},
        {"name": "@description_term_0", "value": "intelligent"},
        {"name": "@description_term_1", "value": "herders"},
    ]
    expected_query_items = [
        {
            'id': 'vec1',
            'SimilarityScore': 0.123,
            'description': 'I love sci-fi movies.',
            'vector': [0.1, 0.2, 0.3],
            'hash': 'abc123',
            'created_at': '2026-01-01T00:00:00',
            'user_id': 'alice',
        },
        {
            'id': 'vec2',
            'SimilarityScore': 0.623,
            'description': 'I enjoy reading fantasy novels.',
            'vector': [0.2, 0.2, 0.3],
            'hash': 'def456',
            'created_at': '2026-01-02T00:00:00',
            'user_id': 'bob',
        },
    ]
    expected_output_data = [
        OutputData(
            id='vec2', score=0.623,
            payload={
                'description': 'I enjoy reading fantasy novels.',
                'hash': 'def456',
                'created_at': '2026-01-02T00:00:00',
                'user_id': 'bob',
            }
        )
    ]

    queries_and_parameters.append(
        (
            get_kwargs(
                search_type=Constants.HYBRID_SCORE_THRESHOLD,
                vectors=vectors,
                limit=limit,
                full_text_rank_filter=full_text_rank_filter
            ),
            expected_query,
            expected_parameters,
            expected_query_items,
            expected_output_data,
        )
    )

    # Case 2: Hybrid search with weights
    weights = [2, 1]
    expected_query = (
        "SELECT TOP @limit *, VectorDistance(c[@vectorKey], @vector) as SimilarityScore "
        "FROM c "
        "ORDER BY RANK RRF(FullTextScore(c[@description], @description_term_0, @description_term_1), VectorDistance(c[@vectorKey], @vector), @weights)"
    )
    expected_parameters = [
        {"name": "@limit", "value": limit},
        {"name": "@vectorKey", "value": Constants.VECTOR},
        {"name": "@vector", "value": vectors},
        {"name": "@description", "value": Constants.DESCRIPTION},
        {"name": "@description_term_0", "value": "intelligent"},
        {"name": "@description_term_1", "value": "herders"},
        {"name": "@weights", "value": weights},
    ]

    queries_and_parameters.append(
        (
            get_kwargs(
                search_type=Constants.HYBRID_SCORE_THRESHOLD,
                vectors=vectors,
                limit=limit,
                full_text_rank_filter=full_text_rank_filter,
                weights=weights,
            ),
            expected_query,
            expected_parameters,
            expected_query_items,
            expected_output_data,
        )
    )

    return queries_and_parameters

def get_filter_search_queries_and_parameters() -> List[Tuple[Dict[str, Any], str, List[Dict[str, Any]]]]:
    queries_and_parameters = []

    vectors = [0.1, 0.2, 0.3]
    limit = 2
    filters = {"user_id": "alice", "hash": "abc123"}

    expected_query_items = [
        {
            'id': 'vec1',
            'SimilarityScore': 0.123,
            'description': 'I love sci-fi movies.',
            'hash': 'abc123',
            'created_at': '2026-01-01T00:00:00',
            'user_id': 'alice',
        }
    ]
    expected_output_data = [
        OutputData(
            id='vec1', score=0.123,
            payload={
                'description': 'I love sci-fi movies.',
                'hash': 'abc123',
                'created_at': '2026-01-01T00:00:00',
                'user_id': 'alice',
            }
        )
    ]

    # Case 1: filters only
    queries_and_parameters.append((
        get_kwargs(
            search_type=Constants.VECTOR,
            vectors=vectors,
            filters=filters,
            limit=limit,
        ),
        (
            "SELECT TOP @limit *, "
            "VectorDistance(c[@vectorKey], @vector) as SimilarityScore "
            "FROM c "
            "WHERE c.user_id=@filter_value_0 AND c.hash=@filter_value_1 "
            "ORDER BY VectorDistance(c[@vectorKey], @vector)"
        ),
        [
            {"name": "@limit", "value": limit},
            {"name": "@vectorKey", "value": Constants.VECTOR},
            {"name": "@vector", "value": vectors},
            {"name": "@filter_value_0", "value": "alice"},
            {"name": "@filter_value_1", "value": "abc123"},
        ],
        expected_query_items,
        expected_output_data,
    ))

    # Case 2: raw where only (now wrapped in parens to preserve precedence)
    where_expr = "c.user_id='alice'"
    queries_and_parameters.append((
        get_kwargs(
            search_type=Constants.VECTOR,
            vectors=vectors,
            where=where_expr,
            limit=limit,
        ),
        (
            "SELECT TOP @limit *, "
            "VectorDistance(c[@vectorKey], @vector) as SimilarityScore "
            f"FROM c "
            f"WHERE ({where_expr}) "
            "ORDER BY VectorDistance(c[@vectorKey], @vector)"
        ),
        [
            {"name": "@limit", "value": limit},
            {"name": "@vectorKey", "value": Constants.VECTOR},
            {"name": "@vector", "value": vectors},
        ],
        expected_query_items,
        expected_output_data,
    ))

    # Case 3: filters AND where combined with AND
    where_expr = "FullTextContains(c.description, 'sci-fi')"
    queries_and_parameters.append((
        get_kwargs(
            search_type=Constants.VECTOR,
            vectors=vectors,
            filters=filters,
            where=where_expr,
            limit=limit,
        ),
        (
            "SELECT TOP @limit *, "
            "VectorDistance(c[@vectorKey], @vector) as SimilarityScore "
            "FROM c "
            f"WHERE c.user_id=@filter_value_0 AND c.hash=@filter_value_1 AND ({where_expr}) "
            "ORDER BY VectorDistance(c[@vectorKey], @vector)"
        ),
        [
            {"name": "@limit", "value": limit},
            {"name": "@vectorKey", "value": Constants.VECTOR},
            {"name": "@vector", "value": vectors},
            {"name": "@filter_value_0", "value": "alice"},
            {"name": "@filter_value_1", "value": "abc123"},
        ],
        expected_query_items,
        expected_output_data,
    ))

    # Case 4: neither filters nor where — no WHERE clause
    queries_and_parameters.append((
        get_kwargs(
            search_type=Constants.VECTOR,
            vectors=vectors,
            limit=limit,
        ),
        (
            "SELECT TOP @limit *, "
            "VectorDistance(c[@vectorKey], @vector) as SimilarityScore "
            "FROM c ORDER BY VectorDistance(c[@vectorKey], @vector)"
        ),
        [
            {"name": "@limit", "value": limit},
            {"name": "@vectorKey", "value": Constants.VECTOR},
            {"name": "@vector", "value": vectors},
        ],
        expected_query_items,
        expected_output_data,
    ))

    return queries_and_parameters


def get_list_return_values():
    return [
        {
            'id': 'vec1',
            Constants.DESCRIPTION: 'I love sci-fi movies.',
            Constants.VECTOR: [0.1, 0.2, 0.3],
            'hash': 'abc123',
            'created_at': '2026-01-01T00:00:00',
            'user_id': 'alice',
        },
        {
            'id': 'vec2',
            Constants.DESCRIPTION: 'I enjoy reading fantasy novels.',
            Constants.VECTOR: [0.4, 0.5, 0.6],
            'hash': 'def456',
            'created_at': '2026-01-02T00:00:00',
            'user_id': 'bob',
        },
    ]
