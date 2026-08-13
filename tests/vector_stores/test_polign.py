import json
from unittest.mock import MagicMock, patch

import pytest

pytest.importorskip("polign", reason="polign not installed")

from polign import Hit, NotFoundError, Vector, VectorPage

from mem0.vector_stores.polign import PAYLOAD_KEY, OutputData, PolignDB


def _encoded(payload):
    """Metadata dict as PolignDB stores it for the given payload."""
    metadata = {
        k: ("true" if v is True else "false" if v is False else v if isinstance(v, str) else str(v))
        for k, v in payload.items()
        if isinstance(v, (str, int, float, bool)) and not k.startswith("_")
    }
    metadata[PAYLOAD_KEY] = json.dumps(payload)
    return metadata


@pytest.fixture
def mock_client():
    with patch("mem0.vector_stores.polign.PolignClient") as MockClient:
        client_instance = MagicMock()
        MockClient.return_value = client_instance
        yield client_instance


@pytest.fixture
def db(mock_client):
    return PolignDB(
        collection_name="test_col",
        embedding_model_dims=4,
        url="http://localhost:23000",
        batch_size=2,
    )


# ── Initialization ──────────────────────────────────────────────────


class TestInit:
    def test_init_defaults(self, mock_client):
        with patch("mem0.vector_stores.polign.PolignClient") as MockClient:
            db = PolignDB(collection_name="my_col", embedding_model_dims=128)
            MockClient.assert_called_once_with("http://localhost:23000", api_key=None)
        assert db.collection_name == "my_col"
        assert db.embedding_model_dims == 128
        assert db.batch_size == 1000

    def test_init_with_auth(self):
        with patch("mem0.vector_stores.polign.PolignClient") as MockClient:
            PolignDB(
                collection_name="c",
                embedding_model_dims=4,
                url="https://db.example.com:23000",
                api_key="plgn_id_secret",
            )
            MockClient.assert_called_once_with("https://db.example.com:23000", api_key="plgn_id_secret")

    def test_init_api_key_from_env(self, monkeypatch):
        monkeypatch.setenv("POLIGN_API_KEY", "plgn_env_key")
        with patch("mem0.vector_stores.polign.PolignClient") as MockClient:
            PolignDB(collection_name="c", embedding_model_dims=4)
            assert MockClient.call_args.kwargs["api_key"] == "plgn_env_key"

    def test_batch_size_capped_at_server_max(self, mock_client):
        db = PolignDB(collection_name="c", embedding_model_dims=4, batch_size=9000)
        assert db.batch_size == 5000


# ── Payload encoding ────────────────────────────────────────────────


class TestPayloadCodec:
    def test_encode_promotes_scalars_and_keeps_json(self, db):
        payload = {"data": "hello", "user_id": "alice", "count": 3, "flag": True, "nested": {"a": 1}}
        metadata = db._encode_payload(payload)
        assert metadata["data"] == "hello"
        assert metadata["user_id"] == "alice"
        assert metadata["count"] == "3"
        assert metadata["flag"] == "true"
        assert "nested" not in metadata  # non-scalar: only inside the JSON blob
        assert json.loads(metadata[PAYLOAD_KEY]) == payload

    def test_decode_roundtrip(self, db):
        payload = {"data": "hi", "user_id": "u", "score": 0.5, "nested": {"a": [1, 2]}}
        assert db._decode_payload(db._encode_payload(payload)) == payload

    def test_decode_without_payload_key_falls_back_to_raw(self, db):
        assert db._decode_payload({"user_id": "u"}) == {"user_id": "u"}

    def test_decode_malformed_payload_key(self, db):
        assert db._decode_payload({PAYLOAD_KEY: "{not json", "user_id": "u"}) == {"user_id": "u"}


# ── Filter translation ──────────────────────────────────────────────


class TestFilterTranslation:
    def test_none_and_empty(self, db):
        assert db._translate_filters(None) is None
        assert db._translate_filters({}) is None

    def test_equality_and_coercion(self, db):
        assert db._translate_filters({"user_id": "alice"}) == {"user_id": "alice"}
        assert db._translate_filters({"count": 3}) == {"count": "3"}
        assert db._translate_filters({"flag": True}) == {"flag": "true"}

    def test_multiple_keys_anded(self, db):
        result = db._translate_filters({"user_id": "alice", "agent_id": "a1"})
        assert result == {"$and": [{"user_id": "alice"}, {"agent_id": "a1"}]}

    def test_wildcard_maps_to_exists(self, db):
        assert db._translate_filters({"user_id": "*"}) == {"user_id": {"$exists": True}}

    def test_list_shorthand_maps_to_in(self, db):
        assert db._translate_filters({"lang": ["en", "fr"]}) == {"lang": {"$in": ["en", "fr"]}}

    def test_comparison_operators(self, db):
        assert db._translate_filters({"score": {"gte": 0.5}}) == {"score": {"$gte": "0.5"}}
        assert db._translate_filters({"a": {"ne": "x"}}) == {"a": {"$ne": "x"}}
        assert db._translate_filters({"a": {"in": ["x", "y"]}}) == {"a": {"$in": ["x", "y"]}}

    def test_nin_uses_not_in(self, db):
        assert db._translate_filters({"a": {"nin": ["x"]}}) == {"$not": {"a": {"$in": ["x"]}}}

    def test_logical_operators(self, db):
        result = db._translate_filters({"OR": [{"a": "1"}, {"b": "2"}]})
        assert result == {"$or": [{"a": "1"}, {"b": "2"}]}
        result = db._translate_filters({"$or": [{"a": "1"}, {"b": "2"}]})
        assert result == {"$or": [{"a": "1"}, {"b": "2"}]}
        result = db._translate_filters({"NOT": [{"a": "1"}]})
        assert result == {"$not": {"a": "1"}}
        result = db._translate_filters({"AND": [{"a": "1"}, {"b": "2"}]})
        assert result == {"$and": [{"a": "1"}, {"b": "2"}]}

    def test_unsupported_operator_raises(self, db):
        with pytest.raises(ValueError, match="Unsupported filter operator"):
            db._translate_filters({"a": {"icontains": "x"}})


# ── Insert ──────────────────────────────────────────────────────────


class TestInsert:
    def test_insert_batches(self, db, mock_client):
        vectors = [[0.1] * 4, [0.2] * 4, [0.3] * 4]
        payloads = [{"data": f"m{i}", "user_id": "u"} for i in range(3)]
        ids = ["id0", "id1", "id2"]

        db.insert(vectors, payloads=payloads, ids=ids)

        assert mock_client.put_many.call_count == 2  # batch_size=2 → 2+1
        first_batch = mock_client.put_many.call_args_list[0].args[1]
        assert [v.id for v in first_batch] == ["id0", "id1"]
        assert first_batch[0].values == vectors[0]
        assert first_batch[0].metadata["user_id"] == "u"
        assert json.loads(first_batch[0].metadata[PAYLOAD_KEY]) == payloads[0]

    def test_insert_without_ids_or_payloads(self, db, mock_client):
        db.insert([[0.1] * 4])
        batch = mock_client.put_many.call_args.args[1]
        assert batch[0].id == "0"
        assert json.loads(batch[0].metadata[PAYLOAD_KEY]) == {}


# ── Search ──────────────────────────────────────────────────────────


class TestSearch:
    def test_search_converts_distance_to_score(self, db, mock_client):
        payload = {"data": "hello", "user_id": "alice"}
        mock_client.search.return_value = [Hit(id="m1", distance=1.0, metadata=_encoded(payload))]

        results = db.search("q", [0.1] * 4, top_k=5, filters={"user_id": "alice"})

        mock_client.search.assert_called_once_with("test_col", values=[0.1] * 4, k=5, ef=0, filter={"user_id": "alice"})
        assert len(results) == 1
        assert results[0].id == "m1"
        assert results[0].score == pytest.approx(0.5)  # 1 / (1 + 1.0)
        assert results[0].payload == payload

    def test_search_missing_collection_returns_empty(self, db, mock_client):
        mock_client.search.side_effect = NotFoundError("no such collection")
        assert db.search("q", [0.1] * 4) == []

    def test_keyword_search(self, db, mock_client):
        payload = {"data": "quick brown fox"}
        mock_client.search.return_value = [Hit(id="m1", distance=0.0, score=7.3, metadata=_encoded(payload))]

        results = db.keyword_search("fox", top_k=3)

        mock_client.search.assert_called_once_with("test_col", text="fox", k=3, filter=None)
        assert results[0].score == pytest.approx(7.3)

    def test_keyword_search_unavailable_returns_none(self, db, mock_client):
        mock_client.search.side_effect = NotFoundError("no segment index")
        assert db.keyword_search("fox") is None


# ── Get / delete / update ───────────────────────────────────────────


class TestCrud:
    def test_get(self, db, mock_client):
        payload = {"data": "hello"}
        mock_client.get.return_value = Vector(id="m1", values=[0.1] * 4, metadata=_encoded(payload))
        result = db.get("m1")
        mock_client.get.assert_called_once_with("test_col", "m1")
        assert result.id == "m1"
        assert result.payload == payload

    def test_get_missing_returns_none(self, db, mock_client):
        mock_client.get.side_effect = NotFoundError("nope")
        assert db.get("missing") is None

    def test_delete(self, db, mock_client):
        db.delete("m1")
        mock_client.delete.assert_called_once_with("test_col", "m1")

    def test_update_payload_only_keeps_vector(self, db, mock_client):
        mock_client.get.return_value = Vector(id="m1", values=[0.5] * 4, metadata=_encoded({"data": "old"}))
        db.update("m1", payload={"data": "new"})
        args = mock_client.put.call_args
        assert args.args == ("test_col", "m1", [0.5] * 4)
        assert json.loads(args.kwargs["metadata"][PAYLOAD_KEY]) == {"data": "new"}

    def test_update_vector_only_keeps_payload(self, db, mock_client):
        old_metadata = _encoded({"data": "old"})
        mock_client.get.return_value = Vector(id="m1", values=[0.5] * 4, metadata=old_metadata)
        db.update("m1", vector=[0.9] * 4)
        args = mock_client.put.call_args
        assert args.args == ("test_col", "m1", [0.9] * 4)
        assert args.kwargs["metadata"] == old_metadata


# ── List ────────────────────────────────────────────────────────────


class TestList:
    def _page(self, payloads, ids=None, total=None):
        vectors = [
            Vector(id=ids[i] if ids else f"id{i}", values=[0.1], metadata=_encoded(p)) for i, p in enumerate(payloads)
        ]
        return VectorPage(vectors=vectors, total=total if total is not None else len(vectors))

    def test_list_filters_client_side(self, db, mock_client):
        mock_client.list.return_value = self._page([{"data": "a", "user_id": "alice"}, {"data": "b", "user_id": "bob"}])
        [results] = db.list(filters={"user_id": "alice"})
        assert [r.payload["data"] for r in results] == ["a"]

    def test_list_paginates_until_total(self, db, mock_client):
        page1 = self._page([{"data": "a"}, {"data": "b"}], ids=["a", "b"], total=3)
        page2 = self._page([{"data": "c"}], ids=["c"], total=3)
        mock_client.list.side_effect = [page1, page2]
        [results] = db.list(top_k=100)
        assert [r.id for r in results] == ["a", "b", "c"]
        assert mock_client.list.call_count == 2
        assert mock_client.list.call_args_list[1].kwargs["offset"] == 2

    def test_list_respects_top_k(self, db, mock_client):
        mock_client.list.return_value = self._page([{"data": "a"}, {"data": "b"}])
        [results] = db.list(top_k=1)
        assert len(results) == 1

    def test_list_missing_collection_returns_empty(self, db, mock_client):
        mock_client.list.side_effect = NotFoundError("nope")
        assert db.list() == [[]]

    def test_client_side_operator_matching(self, db):
        payload = {"user_id": "alice", "score": 0.7}
        assert db._matches(payload, {"score": {"gte": 0.5}})
        assert not db._matches(payload, {"score": {"lt": 0.5}})
        assert db._matches(payload, {"user_id": "*"})
        assert db._matches(payload, {"user_id": ["alice", "bob"]})
        assert db._matches(payload, {"OR": [{"user_id": "bob"}, {"score": 0.7}]})
        assert not db._matches(payload, {"NOT": [{"user_id": "alice"}]})
        assert db._matches(payload, {"missing": {"nin": ["x"]}})


# ── Collection ops ──────────────────────────────────────────────────


class TestCollectionOps:
    def test_list_cols(self, db, mock_client):
        col = MagicMock()
        col.name = "test_col"
        mock_client.list_collections.return_value = [col]
        assert db.list_cols() == ["test_col"]

    def test_col_info_and_count(self, db, mock_client):
        mock_client.list.return_value = VectorPage(vectors=[], total=42)
        assert db.col_info() == {"name": "test_col", "count": 42}
        assert db.count() == 42

    def test_delete_col_prefers_collection_delete(self, db, mock_client):
        db.delete_col()
        mock_client.delete_collection.assert_called_once_with("test_col")
        mock_client.list.assert_not_called()

    def test_delete_col_falls_back_to_vector_deletes(self, db, mock_client):
        from polign import PolignError

        mock_client.delete_collection.side_effect = PolignError("registry not enabled")
        page = VectorPage(vectors=[Vector(id="a", values=[0.1]), Vector(id="b", values=[0.1])], total=2)
        empty = VectorPage(vectors=[], total=0)
        mock_client.list.side_effect = [page, empty]

        db.reset()

        deleted = [c.args[1] for c in mock_client.delete.call_args_list]
        assert deleted == ["a", "b"]


# ── Output shape ────────────────────────────────────────────────────


def test_output_data_model():
    out = OutputData(id="x", score=0.9, payload={"data": "hi"})
    assert out.id == "x" and out.score == 0.9 and out.payload == {"data": "hi"}
