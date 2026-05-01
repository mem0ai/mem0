"""Unit tests for mem0.vector_stores.moss.

The `moss` SDK is an optional dependency that may not be installed in the test
environment.  We inject a fake `moss` module into sys.modules before importing
the provider so that all lazy `from moss import ...` calls inside the provider
methods resolve to our controlled fakes.
"""
import json
import sys
import unittest
from unittest.mock import AsyncMock, MagicMock


class _FakeDocumentInfo:
    def __init__(self, id, text, metadata=None, embedding=None):
        self.id = id
        self.text = text
        self.metadata = metadata
        self.embedding = embedding


class _FakeOpts:
    """Generic options object — stores kwargs as attributes."""
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


def _make_moss_module():
    mod = MagicMock()
    mod.DocumentInfo = _FakeDocumentInfo
    mod.QueryOptions = _FakeOpts
    mod.MutationOptions = _FakeOpts
    mod.GetDocumentsOptions = _FakeOpts
    return mod


_moss_module = _make_moss_module()
sys.modules["moss"] = _moss_module

# Now safe to import the provider (lazy imports inside methods will resolve)
from mem0.vector_stores.moss import MossVectorStore  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_doc(id, text="mem", metadata=None, score=None):
    doc = MagicMock()
    doc.id = id
    doc.text = text
    doc.metadata = metadata if metadata is not None else {}
    if score is not None:
        doc.score = score
    return doc


def _make_index(name):
    idx = MagicMock()
    idx.name = name
    return idx


def _make_client():
    client = MagicMock()
    client.list_indexes = AsyncMock(return_value=[])
    client.create_index = AsyncMock(return_value=MagicMock())
    client.add_docs = AsyncMock(return_value=MagicMock())
    client.delete_docs = AsyncMock(return_value=MagicMock())
    client.get_docs = AsyncMock(return_value=[])
    client.get_index = AsyncMock(return_value=MagicMock())
    client.delete_index = AsyncMock(return_value=True)
    client.load_index = AsyncMock(return_value="path/to/index")
    client.query = AsyncMock(return_value=MagicMock(docs=[]))
    return client


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestMossVectorStore(unittest.TestCase):
    def setUp(self):
        self.mock_client = _make_client()
        _moss_module.MossClient.return_value = self.mock_client

        self.store = MossVectorStore(
            collection_name="test-mem0",
            project_id="proj_123",
            project_key="key_abc",
            model_id="moss-minilm",
            alpha=0.8,
            load_index_on_init=False,
        )

    # ------------------------------------------------------------------
    # create_col
    # ------------------------------------------------------------------

    def test_create_col_marks_existing_index(self):
        self.mock_client.list_indexes = AsyncMock(return_value=[_make_index("test-mem0")])
        self.store.create_col()
        self.assertTrue(self.store._index_created)

    def test_create_col_defers_when_missing(self):
        self.mock_client.list_indexes = AsyncMock(return_value=[])
        self.store.create_col()
        self.assertFalse(self.store._index_created)
        self.mock_client.create_index.assert_not_called()

    # ------------------------------------------------------------------
    # insert
    # ------------------------------------------------------------------

    def test_insert_creates_index_on_first_call(self):
        self.store._index_created = False
        payload = {"data": "hello", "user_id": "alice"}
        self.store.insert([[0.1, 0.2]], payloads=[payload], ids=["uuid-1"])
        self.mock_client.create_index.assert_called_once()
        args = self.mock_client.create_index.call_args[0]
        self.assertEqual(args[0], "test-mem0")
        self.assertIsInstance(args[1][0], _FakeDocumentInfo)
        self.assertEqual(args[1][0].id, "uuid-1")
        self.assertEqual(args[2], "moss-minilm")
        self.assertTrue(self.store._index_created)

    def test_insert_calls_add_docs_when_index_exists(self):
        self.store._index_created = True
        self.store.insert([[0.1]], payloads=[{"data": "world", "user_id": "bob"}], ids=["uuid-2"])
        self.mock_client.add_docs.assert_called_once()
        self.mock_client.create_index.assert_not_called()

    def test_insert_payload_stored_as_json_in_metadata(self):
        self.store._index_created = False
        payload = {"data": "test memory", "user_id": "alice", "score": 0.9}
        self.store.insert([[0.1]], payloads=[payload], ids=["m1"])
        doc_arg = self.mock_client.create_index.call_args[0][1][0]
        self.assertEqual(doc_arg.text, "test memory")
        stored = json.loads(doc_arg.metadata["_payload"])
        self.assertEqual(stored["user_id"], "alice")
        self.assertEqual(stored["score"], 0.9)

    def test_insert_metadata_stringifies_values(self):
        self.store._index_created = True
        payload = {"data": "x", "count": 42, "active": True}
        self.store.insert([[0.1]], payloads=[payload], ids=["m1"])
        doc_arg = self.mock_client.add_docs.call_args[0][1][0]
        self.assertEqual(doc_arg.metadata["count"], "42")
        self.assertEqual(doc_arg.metadata["active"], "True")

    def test_insert_reloads_loaded_index(self):
        self.store._index_created = True
        self.store._index_loaded = True
        self.store.insert([[0.1]], payloads=[{"data": "x"}], ids=["m1"])
        self.mock_client.load_index.assert_called_once_with("test-mem0")

    # ------------------------------------------------------------------
    # search
    # ------------------------------------------------------------------

    def test_search_returns_empty_when_index_not_created(self):
        self.store._index_created = False
        result = self.store.search("query", [0.1, 0.2])
        self.assertEqual(result, [])
        self.mock_client.query.assert_not_called()

    def test_search_calls_query_with_correct_params(self):
        self.store._index_created = True
        self.mock_client.query = AsyncMock(return_value=MagicMock(docs=[]))
        self.store.search("find something", [0.1], top_k=3)
        call_args = self.mock_client.query.call_args[0]
        self.assertEqual(call_args[0], "test-mem0")
        self.assertEqual(call_args[1], "find something")
        opts = call_args[2]
        self.assertEqual(opts.top_k, 3)
        self.assertAlmostEqual(opts.alpha, 0.8)
        self.assertIsNone(opts.filter)

    def test_search_returns_output_payloads(self):
        self.store._index_created = True
        payload = {"data": "mem text", "user_id": "alice"}
        doc = _make_doc("uuid-1", "mem text", {"_payload": json.dumps(payload)}, score=0.91)
        self.mock_client.query = AsyncMock(return_value=MagicMock(docs=[doc]))
        results = self.store.search("q", [0.1], top_k=1)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].id, "uuid-1")
        self.assertAlmostEqual(results[0].score, 0.91)
        self.assertEqual(results[0].payload["user_id"], "alice")

    def test_search_with_filters_loads_index_and_passes_filter(self):
        self.store._index_created = True
        self.store._index_loaded = False
        self.mock_client.query = AsyncMock(return_value=MagicMock(docs=[]))
        self.store.search("q", [0.1], filters={"user_id": "alice"})
        self.mock_client.load_index.assert_called_once_with("test-mem0")
        opts = self.mock_client.query.call_args[0][2]
        self.assertIsNotNone(opts.filter)
        self.assertEqual(opts.filter, {"field": "user_id", "condition": {"$eq": "alice"}})

    def test_search_skips_load_when_already_loaded(self):
        self.store._index_created = True
        self.store._index_loaded = True
        self.mock_client.query = AsyncMock(return_value=MagicMock(docs=[]))
        self.store.search("q", [0.1], filters={"user_id": "alice"})
        self.mock_client.load_index.assert_not_called()

    # ------------------------------------------------------------------
    # delete
    # ------------------------------------------------------------------

    def test_delete_calls_delete_docs(self):
        self.store.delete("uuid-5")
        self.mock_client.delete_docs.assert_called_once_with("test-mem0", ["uuid-5"])

    def test_delete_stringifies_id(self):
        self.store.delete(42)
        self.mock_client.delete_docs.assert_called_once_with("test-mem0", ["42"])

    # ------------------------------------------------------------------
    # update
    # ------------------------------------------------------------------

    def test_update_calls_add_docs_upsert(self):
        self.store.update("uuid-3", payload={"data": "updated", "user_id": "alice"})
        self.mock_client.add_docs.assert_called_once()
        doc_arg = self.mock_client.add_docs.call_args[0][1][0]
        self.assertEqual(doc_arg.id, "uuid-3")
        self.assertEqual(doc_arg.text, "updated")

    def test_update_noop_when_no_payload(self):
        self.store.update("uuid-3", vector=[0.1, 0.2])
        self.mock_client.add_docs.assert_not_called()

    # ------------------------------------------------------------------
    # get
    # ------------------------------------------------------------------

    def test_get_returns_none_when_index_not_created(self):
        self.store._index_created = False
        result = self.store.get("uuid-1")
        self.assertIsNone(result)

    def test_get_fetches_by_id(self):
        self.store._index_created = True
        payload = {"data": "a memory", "user_id": "alice"}
        doc = _make_doc("uuid-1", "a memory", {"_payload": json.dumps(payload)})
        self.mock_client.get_docs = AsyncMock(return_value=[doc])
        result = self.store.get("uuid-1")
        self.assertEqual(result.id, "uuid-1")
        self.assertEqual(result.payload["data"], "a memory")
        # Verify GetDocumentsOptions was constructed with the right id
        get_opts = self.mock_client.get_docs.call_args[0][1]
        self.assertEqual(get_opts.doc_ids, ["uuid-1"])

    def test_get_returns_none_when_not_found(self):
        self.store._index_created = True
        self.mock_client.get_docs = AsyncMock(return_value=[])
        result = self.store.get("missing")
        self.assertIsNone(result)

    # ------------------------------------------------------------------
    # list_cols / col_info / delete_col
    # ------------------------------------------------------------------

    def test_list_cols_delegates_to_list_indexes(self):
        self.mock_client.list_indexes = AsyncMock(return_value=[_make_index("test-mem0")])
        result = self.store.list_cols()
        self.assertEqual(len(result), 1)

    def test_col_info_delegates_to_get_index(self):
        info = MagicMock()
        self.mock_client.get_index = AsyncMock(return_value=info)
        result = self.store.col_info()
        self.mock_client.get_index.assert_called_once_with("test-mem0")
        self.assertEqual(result, info)

    def test_delete_col_clears_state_flags(self):
        self.store._index_created = True
        self.store._index_loaded = True
        self.store.delete_col()
        self.mock_client.delete_index.assert_called_once_with("test-mem0")
        self.assertFalse(self.store._index_created)
        self.assertFalse(self.store._index_loaded)

    # ------------------------------------------------------------------
    # list
    # ------------------------------------------------------------------

    def test_list_returns_empty_tuple_when_not_created(self):
        self.store._index_created = False
        result, offset = self.store.list()
        self.assertEqual(result, [])
        self.assertIsNone(offset)

    def test_list_returns_all_docs(self):
        self.store._index_created = True
        payload = {"data": "mem", "user_id": "alice"}
        doc = _make_doc("m1", "mem", {"_payload": json.dumps(payload)})
        self.mock_client.get_docs = AsyncMock(return_value=[doc])
        results, offset = self.store.list(top_k=10)
        self.assertEqual(len(results), 1)
        self.assertIsNone(offset)
        self.assertEqual(results[0].id, "m1")

    def test_list_filters_client_side(self):
        self.store._index_created = True
        docs = [
            _make_doc("m1", "x", {"_payload": json.dumps({"data": "x", "user_id": "alice"})}),
            _make_doc("m2", "y", {"_payload": json.dumps({"data": "y", "user_id": "bob"})}),
        ]
        self.mock_client.get_docs = AsyncMock(return_value=docs)
        results, _ = self.store.list(filters={"user_id": "alice"})
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].id, "m1")

    def test_list_respects_top_k(self):
        self.store._index_created = True
        docs = [_make_doc(f"m{i}", "t", {"_payload": json.dumps({"data": "t"})}) for i in range(10)]
        self.mock_client.get_docs = AsyncMock(return_value=docs)
        results, _ = self.store.list(top_k=3)
        self.assertEqual(len(results), 3)

    # ------------------------------------------------------------------
    # reset
    # ------------------------------------------------------------------

    def test_reset_deletes_col_and_clears_flags(self):
        self.store._index_created = True
        self.store._index_loaded = True
        self.store.reset()
        self.mock_client.delete_index.assert_called_once_with("test-mem0")
        self.assertFalse(self.store._index_created)
        self.assertFalse(self.store._index_loaded)

    # ------------------------------------------------------------------
    # load_index_on_init
    # ------------------------------------------------------------------

    def test_load_index_on_init_loads_when_index_exists(self):
        client2 = _make_client()
        client2.list_indexes = AsyncMock(return_value=[_make_index("eager")])
        _moss_module.MossClient.return_value = client2

        store = MossVectorStore(
            collection_name="eager",
            project_id="p",
            project_key="k",
            load_index_on_init=True,
        )
        client2.load_index.assert_called_once_with("eager")
        self.assertTrue(store._index_loaded)

    def test_load_index_on_init_skipped_when_index_missing(self):
        client2 = _make_client()
        client2.list_indexes = AsyncMock(return_value=[])
        _moss_module.MossClient.return_value = client2

        store = MossVectorStore(
            collection_name="newindex",
            project_id="p",
            project_key="k",
            load_index_on_init=True,
        )
        client2.load_index.assert_not_called()
        self.assertFalse(store._index_loaded)

    # ------------------------------------------------------------------
    # Filter conversion: _convert_filters
    # ------------------------------------------------------------------

    def test_convert_filters_simple_equality(self):
        result = self.store._convert_filters({"user_id": "alice"})
        self.assertEqual(result, {"field": "user_id", "condition": {"$eq": "alice"}})

    def test_convert_filters_list_shorthand(self):
        result = self.store._convert_filters({"user_id": ["alice", "bob"]})
        self.assertEqual(result, {"field": "user_id", "condition": {"$in": ["alice", "bob"]}})

    def test_convert_filters_operator_dict_range(self):
        result = self.store._convert_filters({"score": {"gt": 5, "lte": 10}})
        cond = result["condition"]
        self.assertEqual(cond["$gt"], 5)
        self.assertEqual(cond["$lte"], 10)

    def test_convert_filters_and(self):
        f = {"AND": [{"user_id": "alice"}, {"agent_id": "a1"}]}
        result = self.store._convert_filters(f)
        self.assertIn("$and", result)
        self.assertEqual(len(result["$and"]), 2)

    def test_convert_filters_or(self):
        f = {"OR": [{"user_id": "alice"}, {"user_id": "bob"}]}
        result = self.store._convert_filters(f)
        self.assertIn("$or", result)
        self.assertEqual(len(result["$or"]), 2)

    def test_convert_filters_not_skipped(self):
        f = {"NOT": [{"user_id": "alice"}]}
        result = self.store._convert_filters(f)
        self.assertIsNone(result)

    def test_convert_filters_wildcard_returns_none(self):
        result = self.store._convert_filters({"user_id": "*"})
        self.assertIsNone(result)

    def test_convert_filters_normalizes_dollar_prefix(self):
        f = {"$and": [{"user_id": "alice"}, {"agent_id": "a1"}]}
        result = self.store._convert_filters(f)
        self.assertIn("$and", result)
        self.assertEqual(len(result["$and"]), 2)

    def test_convert_filters_ne_operator(self):
        result = self.store._convert_filters({"status": {"ne": "deleted"}})
        self.assertEqual(result["condition"], {"$ne": "deleted"})

    def test_convert_filters_in_nin(self):
        f_in = self.store._convert_filters({"tag": {"in": ["a", "b"]}})
        self.assertEqual(f_in["condition"], {"$in": ["a", "b"]})
        f_nin = self.store._convert_filters({"tag": {"nin": ["x"]}})
        self.assertEqual(f_nin["condition"], {"$nin": ["x"]})

    def test_convert_filters_multiple_fields_wrapped_in_and(self):
        result = self.store._convert_filters({"user_id": "alice", "agent_id": "a1"})
        self.assertIn("$and", result)
        fields = {c["field"] for c in result["$and"]}
        self.assertEqual(fields, {"user_id", "agent_id"})

    def test_convert_filters_empty_returns_none(self):
        self.assertIsNone(self.store._convert_filters({}))
        self.assertIsNone(self.store._convert_filters(None))

    # ------------------------------------------------------------------
    # Client-side payload matching: _match_payload
    # ------------------------------------------------------------------

    def test_match_payload_simple_eq(self):
        p = {"user_id": "alice", "score": 5}
        self.assertTrue(self.store._match_payload(p, {"user_id": "alice"}))
        self.assertFalse(self.store._match_payload(p, {"user_id": "bob"}))

    def test_match_payload_in_operator(self):
        p = {"user_id": "alice"}
        self.assertTrue(self.store._match_payload(p, {"user_id": {"in": ["alice", "bob"]}}))
        self.assertFalse(self.store._match_payload(p, {"user_id": {"in": ["charlie"]}}))

    def test_match_payload_and(self):
        p = {"user_id": "alice", "agent_id": "a1"}
        self.assertTrue(self.store._match_payload(p, {"AND": [{"user_id": "alice"}, {"agent_id": "a1"}]}))
        self.assertFalse(self.store._match_payload(p, {"AND": [{"user_id": "alice"}, {"agent_id": "a2"}]}))

    def test_match_payload_or(self):
        p = {"user_id": "alice"}
        self.assertTrue(self.store._match_payload(p, {"OR": [{"user_id": "alice"}, {"user_id": "bob"}]}))
        self.assertFalse(self.store._match_payload(p, {"OR": [{"user_id": "charlie"}, {"user_id": "dave"}]}))

    def test_match_payload_not(self):
        p = {"user_id": "alice"}
        self.assertTrue(self.store._match_payload(p, {"NOT": [{"user_id": "bob"}]}))
        self.assertFalse(self.store._match_payload(p, {"NOT": [{"user_id": "alice"}]}))

    def test_match_payload_gt_lt(self):
        p = {"score": 7}
        self.assertTrue(self.store._match_payload(p, {"score": {"gt": 5}}))
        self.assertFalse(self.store._match_payload(p, {"score": {"gt": 10}}))
        self.assertTrue(self.store._match_payload(p, {"score": {"lte": 7}}))

    # ------------------------------------------------------------------
    # _doc_to_output round-trip
    # ------------------------------------------------------------------

    def test_doc_to_output_parses_payload_json(self):
        payload = {"data": "remember this", "user_id": "alice", "score": 0.88}
        doc = _make_doc("m1", "remember this", {"_payload": json.dumps(payload)}, score=0.75)
        out = self.store._doc_to_output(doc, score=0.75)
        self.assertEqual(out.id, "m1")
        self.assertAlmostEqual(out.score, 0.75)
        self.assertEqual(out.payload["user_id"], "alice")
        self.assertEqual(out.payload["score"], 0.88)

    def test_doc_to_output_falls_back_on_bad_json(self):
        doc = _make_doc("m1", "t", {"_payload": "NOT_JSON", "user_id": "alice"})
        out = self.store._doc_to_output(doc)
        self.assertIn("user_id", out.payload)

    def test_doc_to_output_handles_no_metadata(self):
        doc = _make_doc("m1", "t", None)
        out = self.store._doc_to_output(doc)
        self.assertEqual(out.payload, {})

    def test_doc_to_output_fallback_excludes_payload_key(self):
        """When _payload JSON is invalid, _payload key itself should not appear in fallback dict."""
        doc = _make_doc("m1", "t", {"_payload": "BAD", "user_id": "u1"})
        out = self.store._doc_to_output(doc)
        self.assertNotIn("_payload", out.payload)
        self.assertIn("user_id", out.payload)


if __name__ == "__main__":
    unittest.main()
