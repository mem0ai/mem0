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


@pytest.fixture
@patch("mem0.vector_stores.azure_cosmos_db_no_sql.CosmosClient")
def cosmos_db_client_fixture(mock_cosmos_client):
    mock_client = mock_cosmos_client.return_value
    mock_db = mock_client.create_database_if_not_exists.return_value
    mock_collection = mock_db.create_container_if_not_exists.return_value

    azure_cosmos_db_nosql_vector = AzureCosmosDBNoSql(
        cosmos_client=mock_client,
        indexing_policy=get_vector_indexing_policy("flat"),
        cosmos_database_properties={},
        cosmos_collection_properties={Constants.PARTITION_KEY: PARTITION_KEY_VALUE},
        vector_properties=get_vector_properties("/vector", "float32", VECTOR_DIMENSION, "cosine"),
        vector_search_fields = get_vector_search_fields(
            text_field=Constants.DESCRIPTION, vector_field=Constants.VECTOR
        ),
        database_name=DATABASE_NAME,
        collection_name=COLLECTION_NAME,
        full_text_policy=get_full_text_policy(),
        full_text_search_enabled=True,
    )

    mock_db.create_database_if_not_exists.call_count = 0
    mock_db.create_container_if_not_exists.call_count = 0

    return azure_cosmos_db_nosql_vector, mock_collection, mock_db


def test_initialize_create_col(cosmos_db_client_fixture):
    cosmos_db_vector, mock_collection, mock_db = cosmos_db_client_fixture

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


def test_validate_collection_exists(cosmos_db_client_fixture):
    cosmos_db_vector, mock_collection, mock_db = cosmos_db_client_fixture

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

    # check if validation fails when cosmos_collection_properties is None or does not contain partition key
    expected_error_msg = f"{Constants.PARTITION_KEY} cannot be null or empty for a collection."
    original_cosmos_container_properties = cosmos_db_vector._cosmos_collection_properties
    with pytest.raises(ValueError, match=expected_error_msg):
        cosmos_db_vector._cosmos_collection_properties = None
        cosmos_db_vector._validate_create_collection()
    with pytest.raises(ValueError, match=expected_error_msg):
        cosmos_db_vector._cosmos_collection_properties = {Constants.PARTITION_KEY: None}
        cosmos_db_vector._validate_create_collection()
    cosmos_db_vector._cosmos_collection_properties = original_cosmos_container_properties


def test_insert(cosmos_db_client_fixture):
    cosmos_db_vector, mock_collection, mock_db = cosmos_db_client_fixture

    vectors = [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]
    meta_data_key = cosmos_db_vector._metadata_key
    payloads = [
        {
            Constants.DESCRIPTION: "Border Collies are intelligent, ",
            meta_data_key: {
                "a": 1,
                "origin": "Border Collies were developed in the border "
                "region between Scotland and England.",
            },
        },
        {
            Constants.DESCRIPTION: "energetic herders skilled in outdoor activities.",
            meta_data_key: {
                "a": 2,
                "origin": "Golden Retrievers originated in Scotland in "
                "the mid-19th century.",
            },
        },
    ]

    ids = ["vec1", "vec2"]

    cosmos_db_vector.insert(vectors=vectors, payloads=payloads, ids=ids)

    assert mock_collection.create_item.call_count == 2
    mock_collection.create_item.assert_any_call({
        "id": "vec1",
        Constants.DESCRIPTION: "Border Collies are intelligent, ",
        Constants.VECTOR: [0.1, 0.2, 0.3],
        meta_data_key: {
            "a": 1,
            "origin": "Border Collies were developed in the border "
            "region between Scotland and England.",
        },
    })
    mock_collection.create_item.assert_any_call({
        "id": "vec2",
        Constants.DESCRIPTION: "energetic herders skilled in outdoor activities.",
        Constants.VECTOR: [0.4, 0.5, 0.6],
        meta_data_key: {
            "a": 2,
            "origin": "Golden Retrievers originated in Scotland in "
            "the mid-19th century.",
        },
    })

def test_insert_invalid_inputs(cosmos_db_client_fixture):
    cosmos_db_vector, mock_collection, mock_db = cosmos_db_client_fixture

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
    cosmos_db_vector, mock_collection, mock_db = cosmos_db_client_fixture

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
    cosmos_db_vector, mock_collection, mock_db = cosmos_db_client_fixture


    # Full text search
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
    cosmos_db_vector, mock_collection, mock_db = cosmos_db_client_fixture

    mock_collection.query_items.return_value = MagicMock(matched_count=1)

    # Hybrid search
    for kwargs, query, parameters, query_item, output_data in get_hybrid_search_queries_and_parameters():
        mock_collection.query_items.return_value = query_item

        actual_output_data = cosmos_db_vector.search(**kwargs)
        mock_collection.query_items.assert_called_with(
            query=query,
            parameters=parameters,
            enable_cross_partition_query=True,
        )
        assert actual_output_data == output_data


def test_search_with_errors(cosmos_db_client_fixture):
    cosmos_db_vector, mock_collection, mock_db = cosmos_db_client_fixture

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
    error_message = "'return_with_vectors' can only be True for vector search types using vector embeddings."
    with pytest.raises(ValueError, match=error_message):
        cosmos_db_vector.search(
            search_type=Constants.FULL_TEXT_SEARCH,
            return_with_vectors=True,
        )

    # Test missing full_text_rank_filter for Full Text Ranking
    search_type = Constants.FULL_TEXT_RANKING
    error_message = f"'full_text_rank_filter' required for {search_type}."
    with pytest.raises(ValueError, match=error_message):
        cosmos_db_vector.search(search_type=search_type)


def test_delete(cosmos_db_client_fixture):
    cosmos_db_vector, mock_collection, mock_db = cosmos_db_client_fixture

    vector_id = "vec1"
    cosmos_db_vector.delete(vector_id=vector_id, partition_key_value=vector_id)

    mock_collection.delete_item.assert_called_once_with(
        item=vector_id,
        partition_key=vector_id
    )

def test_delete_cosmos_resource_not_found(cosmos_db_client_fixture):
    """Test that CosmosResourceNotFoundError is raised and handled in delete."""
    cosmos_db_vector, mock_collection, mock_db = cosmos_db_client_fixture
    from mem0.vector_stores.azure_cosmos_db_no_sql import CosmosResourceNotFoundError
    vector_id = "vec_not_found"
    # Correctly instantiate with int status_code and str message
    mock_collection.delete_item.side_effect = CosmosResourceNotFoundError(404, "Not found")
    with pytest.raises(CosmosResourceNotFoundError):
        cosmos_db_vector.delete(vector_id=vector_id, partition_key_value=vector_id)


def test_update(cosmos_db_client_fixture):
    cosmos_db_vector, mock_collection, mock_db = cosmos_db_client_fixture
    vector_id = "id1"
    updated_vector = [0.3] * 1536
    updated_payload = {"name": "updated_vector"}
    expected_item = cosmos_db_vector._create_item_to_insert(
        vector=updated_vector,
        payload=updated_payload,
        id=vector_id,
    )
    mock_collection.upsert_item.return_value = MagicMock(matched_count=1)

    cosmos_db_vector.update(
        vector_id=vector_id,
        partition_key_value=vector_id,
        vector=updated_vector,
        payload=updated_payload)
    mock_collection.upsert_item.assert_called_once_with(body=expected_item)


def test_get(cosmos_db_client_fixture):
    cosmos_db_vector, mock_collection, mock_db = cosmos_db_client_fixture

    # Insert item to be retrieved
    vector_id = "id1"
    vector = [0.3] * 1536
    metadata_key = cosmos_db_vector._metadata_key
    metadata = {"a": "Sample metadata."}
    payload = {Constants.DESCRIPTION: "description text", metadata_key: metadata}
    created_item = cosmos_db_vector._create_item_to_insert(
        vector=vector,
        payload=payload,
        id=vector_id,
    )

    mock_collection.read_item.return_value = created_item

    result = cosmos_db_vector.get(vector_id=vector_id, partition_key_value=vector_id)

    # Construct expected payload
    text_key = cosmos_db_vector._text_key
    vector_key = cosmos_db_vector._vector_key
    expected_payload = {
        text_key: payload[text_key],
        metadata_key: payload[metadata_key],
        vector_key: vector,
    }

    assert result.id == vector_id
    assert result.score == 0.0  # Score is set to 0.0 by default
    assert result.payload == expected_payload
    mock_collection.read_item.assert_called_once_with(
        item=vector_id,
        partition_key=vector_id,
    )


def test_list_cols(cosmos_db_client_fixture):
    cosmos_db_vector, mock_collection, mock_db = cosmos_db_client_fixture

    mock_db.list_containers.return_value = [
        {"id": "collection1"},
        {"id": "collection2"},
    ]

    collections = cosmos_db_vector.list_cols()

    assert collections == ["collection1", "collection2"]
    mock_db.list_containers.assert_called_once()


def test_delete_col(cosmos_db_client_fixture):
    cosmos_db_vector, mock_collection, mock_db = cosmos_db_client_fixture

    cosmos_db_vector.delete_col()

    mock_db.delete_container.assert_called_once_with(
        container=cosmos_db_vector._collection_name
    )


def test_col_info(cosmos_db_client_fixture):
    cosmos_db_vector, mock_collection, mock_db = cosmos_db_client_fixture
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
    cosmos_db_vector, mock_collection, mock_db = cosmos_db_client_fixture

    mock_collection.query_items.return_value = get_list_return_values()

    # Test without filters and limit
    results = cosmos_db_vector.list()
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
    cosmos_db_vector, mock_collection, mock_db = cosmos_db_client_fixture

    cosmos_db_vector.reset()

    mock_db.delete_container.assert_called_once_with(
        container=cosmos_db_vector._collection_name
    )
    mock_db.create_container_if_not_exists.assert_called_once()


def test_vector_search_fields_none_raises_value_error():
    """Test that ValueError is raised if vector_search_fields is None in AzureCosmosDBNoSql."""
    # Provide required arguments, but vector_search_fields is None
    with pytest.raises(ValueError, match="vector_search_fields cannot be null"):
        AzureCosmosDBNoSql(
            cosmos_client=MagicMock(),
            indexing_policy={},
            cosmos_database_properties={},
            cosmos_collection_properties={"partition_key": "pk"},
            vector_properties={},
            vector_search_fields=None,  # This should trigger the ValueError
            database_name="db",
            collection_name="col",
            full_text_policy=None,
            full_text_search_enabled=False,
        )


## Helper functions to generate expected queries and parameters

def get_kwargs(
        search_type: str,
        vectors: Optional[List[float]] = None,
        limit: Optional[int] = None,
        return_with_vectors: Optional[bool] = None,
        full_text_rank_filter: Optional[List[Dict[str,str]]] = None,
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
        "SELECT TOP @limit c.id as id, c[@description] as description, c[@metadata] as metadata, VectorDistance(c[@vectorKey], @vector) as SimilarityScore "
        "FROM c ORDER BY VectorDistance(c[@vectorKey], @vector)"
    )
    expected_parameters = [
        {"name": "@limit", "value": limit},
        {"name": "@description", "value": Constants.DESCRIPTION},
        {"name": "@metadata", "value": Constants.METADATA},
        {"name": "@vectorKey", "value": Constants.VECTOR},
        {"name": "@vector", "value": vectors},
    ]
    expected_query_items = [
        {
            'id': 'vec1',
            'SimilarityScore': 0.123,
            'description': 'Sample description for vector 1.',
            'metadata': {'a': 1, 'b': 2, 'c': 3}
        },
        {
            'id': 'vec2',
            'SimilarityScore': 0.223,
            'description': 'Sample description for vector 2.',
            'metadata': {'a': 2, 'b': 2, 'c': 3}
        }
    ]
    expected_output_data = [
        OutputData(
            id='vec1', score=0.123,
            payload={
                'description': 'Sample description for vector 1.',
                'metadata': {'a': 1, 'b': 2, 'c': 3}
            }
        ),
        OutputData(
            id='vec2', score=0.223,
            payload={
                'description': 'Sample description for vector 2.',
                'metadata': {'a': 2, 'b': 2, 'c': 3}
            }
        )
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
        "SELECT TOP @limit c.id as id, c[@description] as description, c[@metadata] as metadata, c[@vectorKey] as vector, VectorDistance(c[@vectorKey], @vector) as SimilarityScore "
        "FROM c ORDER BY VectorDistance(c[@vectorKey], @vector)"
    )
    expected_parameters = [
        {"name": "@limit", "value": limit},
        {"name": "@description", "value": Constants.DESCRIPTION},
        {"name": "@metadata", "value": Constants.METADATA},
        {"name": "@vectorKey", "value": Constants.VECTOR},
        {"name": "@vector", "value": vectors},
    ]
    expected_query_items = [
        {
            'id': 'vec1',
            'SimilarityScore': 0.123,
            'description': 'Sample description for vector 1.',
            'vector': [0.1, 0.2, 0.3],
            'metadata': {'a': 1, 'b': 2, 'c': 3}
        },
        {
            'id': 'vec2',
            'SimilarityScore': 0.223,
            'description': 'Sample description for vector 2.',
            'vector': [0.2, 0.2, 0.3],
            'metadata': {'a': 2, 'b': 2, 'c': 3}
        }
    ]
    expected_output_data = [
        OutputData(
            id='vec1', score=0.123,
            payload={
                'description': 'Sample description for vector 1.',
                'vector': [0.1, 0.2, 0.3],
                'metadata': {'a': 1, 'b': 2, 'c': 3},
            }
        ),
        OutputData(
            id='vec2', score=0.223,
            payload={
                'description': 'Sample description for vector 2.',
                'vector': [0.2, 0.2, 0.3],
                'metadata': {'a': 2, 'b': 2, 'c': 3},
            }
        )
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
        "SELECT c.id as id, c[@description] as description, c[@metadata] as metadata, VectorDistance(c[@vectorKey], @vector) as SimilarityScore "
        "FROM c ORDER BY VectorDistance(c[@vectorKey], @vector) "
        f"{off_set_limit}"
    )
    expected_parameters = [
        {"name": "@description", "value": Constants.DESCRIPTION},
        {"name": "@metadata", "value": Constants.METADATA},
        {"name": "@vectorKey", "value": Constants.VECTOR},
        {"name": "@vector", "value": vectors},
    ]
    expected_query_items = [
        {
            'id': 'vec1',
            'SimilarityScore': 0.123,
            'description': 'Sample description for vector 1.',
            'vector': [0.1, 0.2, 0.3],
            'metadata': {'a': 1, 'b': 2, 'c': 3}
        }
    ]
    expected_output_data = [
        OutputData(
            id='vec1', score=0.123,
            payload={
                'description': 'Sample description for vector 1.',
                'metadata': {'a': 1, 'b': 2, 'c': 3}
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

    # Case 5: With where filter
    where_filter = "c.metadata.a=1"
    expected_query = (
        "SELECT TOP @limit c.id as id, c[@description] as description, c[@metadata] as metadata, VectorDistance(c[@vectorKey], @vector) as SimilarityScore "
        "FROM c "
        "WHERE c.metadata.a=1 "
        "ORDER BY VectorDistance(c[@vectorKey], @vector)"
    )
    expected_parameters = [
        {"name": "@limit", "value": limit},
        {"name": "@description", "value": Constants.DESCRIPTION},
        {"name": "@metadata", "value": Constants.METADATA},
        {"name": "@vectorKey", "value": Constants.VECTOR},
        {"name": "@vector", "value": vectors},
    ]
    expected_query_items = [
        {
            'id': 'vec1',
            'SimilarityScore': 0.123,
            'description': 'Sample description for vector 1.',
            'vector': [0.1, 0.2, 0.3],
            'metadata': {'a': 1, 'b': 2, 'c': 3}
        }
    ]
    expected_output_data = [
        OutputData(
            id='vec1', score=0.123,
            payload={
                'description': 'Sample description for vector 1.',
                'metadata': {'a': 1, 'b': 2, 'c': 3}
            }
        )
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

    # Case 6: Simple Vector search with k
    expected_query = (
        "SELECT TOP @limit c.id as id, c[@description] as description, c[@metadata] as metadata, VectorDistance(c[@vectorKey], @vector) as SimilarityScore "
        "FROM c ORDER BY VectorDistance(c[@vectorKey], @vector)"
    )
    expected_parameters = [
        {"name": "@limit", "value": limit},
        {"name": "@description", "value": Constants.DESCRIPTION},
        {"name": "@metadata", "value": Constants.METADATA},
        {"name": "@vectorKey", "value": Constants.VECTOR},
        {"name": "@vector", "value": vectors},
    ]
    expected_query_items = [
        {
            'id': 'vec1',
            'SimilarityScore': 0.123,
            'description': 'Sample description for vector 1.',
            'metadata': {'a': 1, 'b': 2, 'c': 3}
        },
        {
            'id': 'vec2',
            'SimilarityScore': 0.623,
            'description': 'Sample description for vector 2.',
            'metadata': {'a': 2, 'b': 2, 'c': 3}
        }
    ]
    expected_output_data = [
        OutputData(
            id='vec2', score=0.623,
            payload={
                'description': 'Sample description for vector 2.',
                'metadata': {'a': 2, 'b': 2, 'c': 3}
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

    # Case 1: Simple full text search
    where = "FullTextContainsAny(c.description, 'intelligent', 'herders')"
    expected_query = (
        "SELECT TOP @limit c.id as id, c[@description] as description, c[@metadata] as metadata "
        "FROM c "
        "WHERE FullTextContainsAny(c.description, 'intelligent', 'herders')"
    )
    expected_parameters = [
        {"name": "@limit", "value": limit},
        {"name": "@description", "value": "description"},
        {"name": "@metadata", "value": "metadata"},
    ]
    expected_query_items = [
        {
            'id': 'vec1',
            'description': 'Sample description for vector 1.',
            'metadata': {'a': 1, 'b': 2, 'c': 3}
        },
        {
            'id': 'vec2',
            'description': 'Sample description for vector 2.',
            'metadata': {'a': 2, 'b': 2, 'c': 3}
        }
    ]
    expected_output_data = [
        OutputData(
            id='vec1', score=0.0,
            payload={
                'description': 'Sample description for vector 1.',
                'metadata': {'a': 1, 'b': 2, 'c': 3}
            }
        ),
        OutputData(
            id='vec2', score=0.0,
            payload={
                'description': 'Sample description for vector 2.',
                'metadata': {'a': 2, 'b': 2, 'c': 3}
            }
        )
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
        "SELECT TOP @limit c.id as id, c[@description] as description "
        "FROM c "
        "ORDER BY RANK FullTextScore(c[@description], @description_term_0, @description_term_1)"
    )
    expected_parameters = [
        {"name": "@limit", "value": limit},
        {"name": "@description", "value": "description"},
        {"name": "@description_term_0", "value": "intelligent"},
        {"name": "@description_term_1", "value": "herders"},
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
            expected_query_items,
            expected_output_data,
        )
    )

    # Case 3: Full text ranking with multiple search fields
    full_text_rank_filter = [
        {"search_field": "description", "search_text": search_text},
        {"search_field": "metadata", "search_text": search_text}
    ]
    expected_query = (
        "SELECT TOP @limit c.id as id, c[@description] as description, c[@metadata] as metadata "
        "FROM c "
        "ORDER BY RANK RRF(FullTextScore(c[@description], @description_term_0, @description_term_1), FullTextScore(c[@metadata], @metadata_term_0, @metadata_term_1))"
    )
    expected_parameters = [
        {"name": "@limit", "value": limit},
        {"name": "@description", "value": "description"},
        {"name": "@metadata", "value": "metadata"},
        {"name": "@description_term_0", "value": "intelligent"},
        {"name": "@description_term_1", "value": "herders"},
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
            expected_query_items,
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
        "SELECT TOP @limit c.id as id, c[@description] as description, c[@metadata] as metadata, VectorDistance(c[@vectorKey], @vector) as SimilarityScore "
        "FROM c "
        "ORDER BY RANK RRF(FullTextScore(c[@description], @description_term_0, @description_term_1), VectorDistance(c[@vectorKey], @vector))"
    )
    expected_parameters = [
        {"name": "@limit", "value": limit},
        {"name": "@description", "value": Constants.DESCRIPTION},
        {"name": "@metadata", "value": Constants.METADATA},
        {"name": "@vectorKey", "value": Constants.VECTOR},
        {"name": "@vector", "value": vectors},
        {"name": "@description_term_0", "value": "intelligent"},
        {"name": "@description_term_1", "value": "herders"},
    ]
    expected_query_items = [
        {
            'id': 'vec1',
            'SimilarityScore': 0.123,
            'description': 'Sample description for vector 1.',
            'vector': [0.1, 0.2, 0.3],
            'metadata': {'a': 1, 'b': 2, 'c': 3}
        },
        {
            'id': 'vec2',
            'SimilarityScore': 0.623,
            'description': 'Sample description for vector 2.',
            'vector': [0.2, 0.2, 0.3],
            'metadata': {'a': 2, 'b': 2, 'c': 3}
        }
    ]
    expected_output_data = [
        OutputData(
            id='vec2', score=0.623,
            payload={
                'description': 'Sample description for vector 2.',
                'metadata': {'a': 2, 'b': 2, 'c': 3}
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
        "SELECT TOP @limit c.id as id, c[@description] as description, c[@metadata] as metadata, VectorDistance(c[@vectorKey], @vector) as SimilarityScore "
        "FROM c "
        "ORDER BY RANK RRF(FullTextScore(c[@description], @description_term_0, @description_term_1), VectorDistance(c[@vectorKey], @vector), @weights)"
    )
    expected_parameters = [
        {"name": "@limit", "value": limit},
        {"name": "@description", "value": Constants.DESCRIPTION},
        {"name": "@metadata", "value": Constants.METADATA},
        {"name": "@vectorKey", "value": Constants.VECTOR},
        {"name": "@vector", "value": vectors},
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

def get_list_return_values():
    return [
        {
            'id': 'vec1',
            Constants.DESCRIPTION: 'Border Collies are intelligent, ',
            Constants.VECTOR: [0.1, 0.2, 0.3],
            'metadata': {
                'a': 1,
                'origin': 'Border Collies were developed in the border region between Scotland and England.',
            },
        },
        {
            'id': 'vec2',
            Constants.DESCRIPTION: 'energetic herders skilled in outdoor activities.',
            Constants.VECTOR: [0.4, 0.5, 0.6],
            'metadata': {
                'a': 2,
                'origin': 'Golden Retrievers originated in Scotland in the mid-19th century.',
            },
        },
    ]

