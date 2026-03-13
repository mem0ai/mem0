import pytest
from unittest.mock import MagicMock

from mem0.vector_stores.cos_vectors import CosVectors


BUCKET_NAME = "test-bucket"
INDEX_NAME = "test-index"
REGION = "ap-guangzhou"
EMBEDDING_DIMS = 1536
SECRET_ID = "test-secret-id"
SECRET_KEY = "test-secret-key"
TOKEN = "test-token"


class FakeCosServiceError(Exception):
    """模拟 CosServiceError，用于测试异常处理逻辑。"""

    def __init__(self, error_code, error_msg="mock error"):
        self._error_code = error_code
        self._error_msg = error_msg
        super().__init__(error_msg)

    def get_error_code(self):
        return self._error_code

    def get_error_msg(self):
        return self._error_msg


@pytest.fixture(autouse=True)
def mock_cos_imports(mocker):
    """模拟 qcloud_cos 模块的导入，避免测试依赖真实的 SDK。"""
    mock_config_cls = mocker.MagicMock(name="CosConfig")
    mock_client_cls = mocker.MagicMock(name="CosVectorsClient")

    mocker.patch("mem0.vector_stores.cos_vectors.CosConfig", mock_config_cls)
    mocker.patch("mem0.vector_stores.cos_vectors.CosVectorsClient", mock_client_cls)
    mocker.patch("mem0.vector_stores.cos_vectors.CosServiceError", FakeCosServiceError)

    return mock_config_cls, mock_client_cls


@pytest.fixture
def mock_cos_client(mock_cos_imports):
    """获取被 mock 的 CosVectorsClient 实例。"""
    _, mock_client_cls = mock_cos_imports
    mock_client = mock_client_cls.return_value
    return mock_client


@pytest.fixture
def mock_embedder(mocker):
    mock_embedder = mocker.MagicMock()
    mock_embedder.return_value.embed.return_value = [0.1, 0.2, 0.3]
    mocker.patch("mem0.utils.factory.EmbedderFactory.create", mock_embedder)
    return mock_embedder


@pytest.fixture
def mock_llm(mocker):
    mock_llm = mocker.MagicMock()
    mocker.patch("mem0.utils.factory.LlmFactory.create", mock_llm)
    mocker.patch("mem0.memory.storage.SQLiteManager", mocker.MagicMock())
    return mock_llm


def _create_store(mock_cos_client):
    """创建 CosVectors 实例的辅助方法。"""
    return CosVectors(
        bucket_name=BUCKET_NAME,
        index_name=INDEX_NAME,
        region=REGION,
        embedding_model_dims=EMBEDDING_DIMS,
        secret_id=SECRET_ID,
        secret_key=SECRET_KEY,
        token=TOKEN,
    )


def test_initialization_creates_resources(mock_cos_client):
    """测试当 bucket 和 index 不存在时，会自动创建它们。"""
    not_found_error = FakeCosServiceError("NotFoundException")
    mock_cos_client.get_vector_bucket.side_effect = not_found_error
    mock_cos_client.get_index.side_effect = not_found_error

    _create_store(mock_cos_client)

    mock_cos_client.create_vector_bucket.assert_called_once_with(
        Bucket=BUCKET_NAME
    )
    mock_cos_client.create_index.assert_called_once_with(
        Bucket=BUCKET_NAME,
        Index=INDEX_NAME,
        DataType="float32",
        Dimension=EMBEDDING_DIMS,
        DistanceMetric="cosine",
    )


def test_initialization_uses_existing_resources(mock_cos_client):
    """测试当 bucket 和 index 已存在时，不会重复创建。"""
    mock_cos_client.get_vector_bucket.return_value = {}
    mock_cos_client.get_index.return_value = {}

    _create_store(mock_cos_client)

    mock_cos_client.create_vector_bucket.assert_not_called()
    mock_cos_client.create_index.assert_not_called()


def test_ensure_bucket_exists_raises_on_other_error(mock_cos_client):
    """测试当 _ensure_bucket_exists 遇到非 NotFoundException 的 CosServiceError 时，会向上抛出。"""
    other_error = FakeCosServiceError("AccessDenied", "access denied")
    mock_cos_client.get_vector_bucket.side_effect = other_error

    with pytest.raises(FakeCosServiceError):
        _create_store(mock_cos_client)


def test_create_col_raises_on_other_error(mock_cos_client):
    """测试当 create_col 遇到非 NotFoundException 的 CosServiceError 时，会向上抛出。"""
    mock_cos_client.get_vector_bucket.return_value = {}
    other_error = FakeCosServiceError("InternalError", "internal error")
    mock_cos_client.get_index.side_effect = other_error

    with pytest.raises(FakeCosServiceError):
        _create_store(mock_cos_client)


def test_insert(mock_cos_client):
    """测试插入向量。"""
    store = _create_store(mock_cos_client)
    vectors = [[0.1, 0.2], [0.3, 0.4]]
    payloads = [{"meta": "data1"}, {"meta": "data2"}]
    ids = ["id1", "id2"]

    store.insert(vectors, payloads, ids)

    mock_cos_client.put_vectors.assert_called_once_with(
        Bucket=BUCKET_NAME,
        Index=INDEX_NAME,
        Vectors=[
            {
                "key": "id1",
                "data": {"float32": [0.1, 0.2]},
                "metadata": {"meta": "data1"},
            },
            {
                "key": "id2",
                "data": {"float32": [0.3, 0.4]},
                "metadata": {"meta": "data2"},
            },
        ],
    )


def test_search(mock_cos_client):
    """测试搜索向量。"""
    mock_cos_client.query_vectors.return_value = (
        {},  # CosVectors 的 query_vectors 返回元组 (response, data)
        {"vectors": [{"key": "id1", "distance": 0.9, "metadata": {"meta": "data1"}}]},
    )
    store = _create_store(mock_cos_client)
    query_vector = [0.1, 0.2]
    results = store.search(query="test", vectors=query_vector, limit=1)

    mock_cos_client.query_vectors.assert_called_once_with(
        Bucket=BUCKET_NAME,
        Index=INDEX_NAME,
        QueryVector={"float32": [0.1, 0.2]},
        TopK=1,
        ReturnMetaData=True,
        ReturnDistance=True,
        Filter=None,
    )
    assert len(results) == 1
    assert results[0].id == "id1"
    assert results[0].score == 0.9


def test_search_with_filters(mock_cos_client):
    """测试带过滤条件的搜索。"""
    mock_cos_client.query_vectors.return_value = (
        {},
        {"vectors": [{"key": "id1", "distance": 0.8, "metadata": {"category": "test"}}]},
    )
    store = _create_store(mock_cos_client)
    filters = {"category": "test"}
    results = store.search(query="test", vectors=[0.1, 0.2], limit=5, filters=filters)

    mock_cos_client.query_vectors.assert_called_once_with(
        Bucket=BUCKET_NAME,
        Index=INDEX_NAME,
        QueryVector={"float32": [0.1, 0.2]},
        TopK=5,
        ReturnMetaData=True,
        ReturnDistance=True,
        Filter=filters,
    )
    assert len(results) == 1
    assert results[0].id == "id1"


def test_get(mock_cos_client):
    """测试通过 ID 获取向量。"""
    mock_cos_client.get_vectors.return_value = (
        {},
        {"vectors": [{"key": "id1", "metadata": {"meta": "data1"}}]},
    )
    store = _create_store(mock_cos_client)
    result = store.get("id1")

    mock_cos_client.get_vectors.assert_called_once_with(
        Bucket=BUCKET_NAME,
        Index=INDEX_NAME,
        keys=["id1"],
        returnData=False,
        returnMetadata=True,
    )
    assert result.id == "id1"
    assert result.payload["meta"] == "data1"


def test_get_not_found(mock_cos_client):
    """测试获取不存在的向量时返回 None。"""
    mock_cos_client.get_vectors.return_value = (
        {},
        {"vectors": []},
    )
    store = _create_store(mock_cos_client)
    result = store.get("nonexistent-id")

    assert result is None


def test_delete(mock_cos_client):
    """测试删除向量。"""
    store = _create_store(mock_cos_client)
    store.delete("id1")

    mock_cos_client.delete_vectors.assert_called_once_with(
        Bucket=BUCKET_NAME, Index=INDEX_NAME, keys=["id1"]
    )


def test_update(mock_cos_client):
    """测试更新向量（底层使用 put_vectors 覆盖写入）。"""
    store = _create_store(mock_cos_client)
    store.update("id1", vector=[0.5, 0.6], payload={"meta": "updated"})

    mock_cos_client.put_vectors.assert_called_once_with(
        Bucket=BUCKET_NAME,
        Index=INDEX_NAME,
        Vectors=[
            {
                "key": "id1",
                "data": {"float32": [0.5, 0.6]},
                "metadata": {"meta": "updated"},
            },
        ],
    )


def test_list_cols(mock_cos_client):
    """测试列出所有 index。"""
    mock_cos_client.list_indexes.return_value = (
        {},
        {"indexes": [{"indexName": "idx1"}, {"indexName": "idx2"}]},
    )
    store = _create_store(mock_cos_client)
    cols = store.list_cols()

    mock_cos_client.list_indexes.assert_called_once_with(Bucket=BUCKET_NAME)
    assert cols == ["idx1", "idx2"]


def test_delete_col(mock_cos_client):
    """测试删除 index。"""
    store = _create_store(mock_cos_client)
    store.delete_col()

    mock_cos_client.delete_index.assert_called_once_with(
        Bucket=BUCKET_NAME, Index=INDEX_NAME
    )


def test_col_info(mock_cos_client):
    """测试获取 index 信息。"""
    mock_cos_client.get_index.return_value = (
        {},
        {"index": {"indexName": INDEX_NAME, "dimension": EMBEDDING_DIMS}},
    )
    store = _create_store(mock_cos_client)
    info = store.col_info()

    assert info["indexName"] == INDEX_NAME
    assert info["dimension"] == EMBEDDING_DIMS


def test_list(mock_cos_client):
    """测试列出所有向量。"""
    mock_cos_client.list_vectors.return_value = (
        {},
        {
            "vectors": [
                {"key": "id1", "metadata": {"meta": "data1"}},
                {"key": "id2", "metadata": {"meta": "data2"}},
            ],
        },
    )
    store = _create_store(mock_cos_client)
    results = store.list()

    mock_cos_client.list_vectors.assert_called_once_with(
        Bucket=BUCKET_NAME,
        Index=INDEX_NAME,
        ReturnData=False,
        ReturnMetaData=True,
        NextToken=None,
        MaxResults=None,
    )
    assert len(results) == 1  # list 返回 [parsed_output]
    assert len(results[0]) == 2
    assert results[0][0].id == "id1"
    assert results[0][1].id == "id2"


def test_list_with_pagination(mock_cos_client):
    """测试分页列出向量。"""
    # 第一次调用返回带 nextToken 的结果
    mock_cos_client.list_vectors.side_effect = [
        (
            {},
            {
                "vectors": [{"key": "id1", "metadata": {"meta": "data1"}}],
                "nextToken": "token123",
            },
        ),
        (
            {},
            {
                "vectors": [{"key": "id2", "metadata": {"meta": "data2"}}],
            },
        ),
    ]
    store = _create_store(mock_cos_client)
    results = store.list()

    assert mock_cos_client.list_vectors.call_count == 2
    assert len(results[0]) == 2
    assert results[0][0].id == "id1"
    assert results[0][1].id == "id2"


def test_list_with_filters_warning(mock_cos_client, caplog):
    """测试 list 传入 filters 时会输出警告日志。"""
    mock_cos_client.list_vectors.return_value = (
        {},
        {"vectors": []},
    )
    store = _create_store(mock_cos_client)

    import logging
    with caplog.at_level(logging.WARNING):
        store.list(filters={"category": "test"})

    assert "does not support metadata filtering" in caplog.text


def test_reset(mock_cos_client):
    """测试重置 index（删除后重新创建）。"""
    not_found_error = FakeCosServiceError("NotFoundException")
    mock_cos_client.get_index.side_effect = not_found_error

    store = _create_store(mock_cos_client)

    # 初始化时 index 不存在，create_index 被调用 1 次
    assert mock_cos_client.create_index.call_count == 1

    # reset 时，delete_col 后 create_col 再次创建
    mock_cos_client.list_vectors.return_value = ({}, {"vectors": []})
    store.reset()

    mock_cos_client.delete_index.assert_called_once_with(
        Bucket=BUCKET_NAME, Index=INDEX_NAME
    )
    assert mock_cos_client.create_index.call_count == 2


def test_endpoint_external(mock_cos_imports):
    """测试外部访问时的 endpoint 生成。"""
    _, mock_client_cls = mock_cos_imports
    mock_client = mock_client_cls.return_value
    mock_client.get_vector_bucket.return_value = {}
    mock_client.get_index.return_value = {}

    store = CosVectors(
        bucket_name=BUCKET_NAME,
        index_name=INDEX_NAME,
        region=REGION,
        embedding_model_dims=EMBEDDING_DIMS,
        secret_id=SECRET_ID,
        secret_key=SECRET_KEY,
        token=TOKEN,
        internal_access=False,
    )

    assert store._get_endpoint() == f"vectors.{REGION}.coslake.com"


def test_endpoint_internal(mock_cos_imports):
    """测试内网访问时的 endpoint 生成。"""
    _, mock_client_cls = mock_cos_imports
    mock_client = mock_client_cls.return_value
    mock_client.get_vector_bucket.return_value = {}
    mock_client.get_index.return_value = {}

    store = CosVectors(
        bucket_name=BUCKET_NAME,
        index_name=INDEX_NAME,
        region=REGION,
        embedding_model_dims=EMBEDDING_DIMS,
        secret_id=SECRET_ID,
        secret_key=SECRET_KEY,
        token=TOKEN,
        internal_access=True,
    )

    assert store._get_endpoint() == f"vectors.{REGION}.internal.tencentcos.com"


def test_parse_output_with_json_string_metadata(mock_cos_client):
    """测试 _parse_output 能正确解析 JSON 字符串格式的 metadata。"""
    store = _create_store(mock_cos_client)
    vectors = [
        {"key": "id1", "distance": 0.95, "metadata": '{"meta": "data1"}'},
    ]
    results = store._parse_output(vectors)

    assert len(results) == 1
    assert results[0].id == "id1"
    assert results[0].score == 0.95
    assert results[0].payload == {"meta": "data1"}


def test_parse_output_with_invalid_json_string_metadata(mock_cos_client):
    """测试 _parse_output 遇到无效 JSON 字符串时，payload 回退为空字典。"""
    store = _create_store(mock_cos_client)
    vectors = [
        {"key": "id1", "distance": 0.8, "metadata": "not-valid-json"},
    ]
    results = store._parse_output(vectors)

    assert len(results) == 1
    assert results[0].id == "id1"
    assert results[0].payload == {}
