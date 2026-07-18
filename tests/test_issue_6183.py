import sys
import types
from pathlib import Path

mem0_package = types.ModuleType("mem0")
mem0_package.__path__ = [str(Path(__file__).resolve().parents[1] / "mem0")]
sys.modules.setdefault("mem0", mem0_package)

try:
    from pymilvus.exceptions import MilvusException
except ModuleNotFoundError:
    pymilvus = types.ModuleType("pymilvus")
    pymilvus_exceptions = types.ModuleType("pymilvus.exceptions")

    class MilvusException(Exception):
        def __init__(self, code=None, message=""):
            super().__init__(message)
            self.code = code
            self.message = message

    class _CollectionSchema:
        def __init__(self, fields, enable_dynamic_field=False):
            self.fields = fields
            self.enable_dynamic_field = enable_dynamic_field
            self.functions = []

        def add_function(self, function):
            self.functions.append(function)

    class _DataType:
        VARCHAR = "VARCHAR"
        FLOAT_VECTOR = "FLOAT_VECTOR"
        JSON = "JSON"
        SPARSE_FLOAT_VECTOR = "SPARSE_FLOAT_VECTOR"

    class _FieldSchema:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    class _Function:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    class _FunctionType:
        BM25 = "BM25"

    class _MilvusClient:
        pass

    pymilvus.CollectionSchema = _CollectionSchema
    pymilvus.DataType = _DataType
    pymilvus.FieldSchema = _FieldSchema
    pymilvus.Function = _Function
    pymilvus.FunctionType = _FunctionType
    pymilvus.MilvusClient = _MilvusClient
    pymilvus_exceptions.MilvusException = MilvusException
    sys.modules["pymilvus"] = pymilvus
    sys.modules["pymilvus.exceptions"] = pymilvus_exceptions

from mem0.configs.vector_stores.milvus import MetricType
from mem0.vector_stores.milvus import MilvusDB


class _Pre25MilvusIndexParams:
    def __init__(self):
        self.indexes = []

    def add_index(self, **kwargs):
        self.indexes.append(kwargs)
        if kwargs["field_name"] == "sparse":
            raise MilvusException(
                code=1100,
                message=(
                    "create index on 104 field is not supported: "
                    "invalid parameter[expected=supported field][actual=create index on 104 field]"
                ),
            )


class _Pre25MilvusClient:
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.created_collections = []

    def has_collection(self, collection_name):
        return False

    def prepare_index_params(self):
        return _Pre25MilvusIndexParams()

    def create_collection(self, **kwargs):
        self.created_collections.append(kwargs)


def test_issue_6183(monkeypatch):
    monkeypatch.setattr("mem0.vector_stores.milvus.MilvusClient", _Pre25MilvusClient)

    db = MilvusDB(
        url="127.0.0.1",
        token="8e4b8ca8cf2c67",
        collection_name="test",
        embedding_model_dims=1536,
        metric_type=MetricType.COSINE,
        db_name="my_database",
    )

    assert db.collection_name == "test"
