import json
import logging

import pytest
from unittest.mock import MagicMock, patch

from mem0.configs.vector_stores.gaussdb import GaussDBConfig
from mem0.utils.factory import VectorStoreFactory
from mem0.vector_stores.configs import VectorStoreConfig
from mem0.vector_stores import gaussdb as gaussdb_module
from mem0.vector_stores.gaussdb import GaussDB


def make_gaussdb(**kwargs):
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    mock_conn.get_parameter_status.return_value = "UTF8"
    mock_cursor.fetchone.return_value = ("UTF8",)
    mock_pool = MagicMock()
    mock_pool.getconn.return_value = mock_conn

    config = {
        "collection_name": "test_collection",
        "embedding_model_dims": 3,
        "auto_create": False,
    }
    config.update(kwargs)

    with patch.object(GaussDB, "_create_connection_pool", return_value=mock_pool):
        with patch.object(GaussDB, "_probe_capabilities"):
            db = GaussDB(**config)
    return db, mock_pool, mock_conn, mock_cursor


def executed_sql(mock_cursor):
    return "\n".join(str(call.args[0]) for call in mock_cursor.execute.call_args_list)


class DummyMap:
    def __iter__(self):
        return iter((("k", "v"),))


# ============================================================
# Config tests
# ============================================================


def test_gaussdb_config_defaults():
    cfg = GaussDBConfig(
        host="localhost",
        port=5432,
        user="test",
        password="test",
    )

    assert cfg.database == "postgres"
    assert cfg.deployment_mode == "centralized"
    assert cfg.vector_index_type == "gsdiskann"
    assert cfg.vector_metric == "cosine"
    assert cfg.collection_name == "mem0"
    assert cfg.schema == "public"
    assert cfg.embedding_model_dims == 1536
    assert cfg.minconn == 1
    assert cfg.maxconn == 5
    assert cfg.auto_create is True
    assert cfg.require_scoped_filters is False


def test_gaussdb_config_accepts_connection_string():
    cfg = GaussDBConfig(connection_string="postgresql://user:pass@localhost:19995/mem0db")

    assert cfg.connection_string == "postgresql://user:pass@localhost:19995/mem0db"


def test_gaussdb_config_accepts_distributed_deployment_mode():
    cfg = GaussDBConfig(
        host="localhost",
        port=5432,
        user="test",
        password="test",
        deployment_mode="distributed",
        embedding_model_dims=512,
    )

    assert cfg.deployment_mode == "distributed"


def test_gaussdb_config_accepts_require_scoped_filters_override():
    cfg = GaussDBConfig(
        host="localhost",
        port=5432,
        user="test",
        password="test",
        require_scoped_filters=True,
    )

    assert cfg.require_scoped_filters is True


def test_gaussdb_config_accepts_metadata_schema():
    cfg = GaussDBConfig(
        host="localhost",
        port=5432,
        user="test",
        password="test",
        metadata_schema={"priority": "number", "title": "text", "flag": "bool"},
    )

    assert cfg.metadata_schema == {"priority": "number", "title": "text", "flag": "bool"}


def test_gaussdb_config_accepts_custom_schema():
    cfg = GaussDBConfig(
        host="localhost",
        port=5432,
        user="test",
        password="test",
        schema="mem0_app",
    )

    assert cfg.schema == "mem0_app"


def test_gaussdb_config_rejects_invalid_schema():
    with pytest.raises(Exception, match="schema"):
        GaussDBConfig(
            host="localhost",
            port=5432,
            user="test",
            password="test",
            schema="bad-schema",
        )


def test_gaussdb_config_rejects_invalid_metadata_schema_type():
    with pytest.raises(Exception, match="metadata_schema"):
        GaussDBConfig(
            host="localhost",
            port=5432,
            user="test",
            password="test",
            metadata_schema={"priority": "decimal"},
        )


def test_gaussdb_config_rejects_centralized_with_too_high_dims():
    with pytest.raises(Exception, match="centralized mode only supports"):
        GaussDBConfig(
            host="localhost",
            port=5432,
            user="test",
            password="test",
            deployment_mode="centralized",
            embedding_model_dims=8192,
        )


def test_gaussdb_config_rejects_distributed_with_high_dims():
    with pytest.raises(Exception):
        GaussDBConfig(
            host="localhost",
            port=5432,
            user="test",
            password="test",
            deployment_mode="distributed",
            embedding_model_dims=2048,
        )


def test_gaussdb_config_rejects_high_dims_with_gsivfflat():
    with pytest.raises(Exception, match="only GsDiskANN supports"):
        GaussDBConfig(
            host="localhost",
            port=5432,
            user="test",
            password="test",
            vector_index_type="gsivfflat",
            embedding_model_dims=2048,
        )


def test_gaussdb_config_rejects_partial_credentials_without_connection_string():
    with pytest.raises(Exception, match="both 'user' and 'password' must be provided together"):
        GaussDBConfig(
            host="localhost",
            port=5432,
            user="test",
        )


def test_gaussdb_config_rejects_partial_host_port_without_connection_string():
    with pytest.raises(Exception, match="both 'host' and 'port' must be provided together"):
        GaussDBConfig(
            user="test",
            password="test",
            host="localhost",
        )


def test_gaussdb_config_rejects_zero_pool_sizes():
    with pytest.raises(Exception, match="minconn must be >= 1"):
        GaussDBConfig(
            host="localhost",
            port=5432,
            user="test",
            password="test",
            minconn=0,
        )

    with pytest.raises(Exception, match="maxconn must be >= 1"):
        GaussDBConfig(
            host="localhost",
            port=5432,
            user="test",
            password="test",
            maxconn=0,
        )


def test_gaussdb_config_reads_connection_from_env(monkeypatch):
    monkeypatch.setenv("GAUSSDB_HOST", "db.example.com")
    monkeypatch.setenv("GAUSSDB_PORT", "19995")
    monkeypatch.setenv("GAUSSDB_DATABASE", "mem0db")
    monkeypatch.setenv("GAUSSDB_USER", "mem0_user")
    monkeypatch.setenv("GAUSSDB_PASSWORD", "secret")

    cfg = GaussDBConfig()

    assert cfg.host == "db.example.com"
    assert cfg.port == 19995
    assert cfg.database == "mem0db"
    assert cfg.user == "mem0_user"
    assert cfg.password == "secret"


def test_gaussdb_config_rejects_extra_fields():
    with pytest.raises(Exception):
        GaussDBConfig(
            host="localhost",
            port=5432,
            user="test",
            password="test",
            unexpected=True,
        )


def test_gaussdb_enable_bm25_alias_tracks_bm25_enabled():
    db, _, _, _ = make_gaussdb()

    assert db.enable_bm25 is True
    db.enable_bm25 = False
    assert db.bm25_enabled is False
    db.bm25_enabled = True
    assert db.enable_bm25 is True


def test_vector_store_config_and_factory_register_gaussdb():
    cfg = VectorStoreConfig(
        provider="gaussdb",
        config={
            "host": "localhost",
            "port": 5432,
            "user": "test",
            "password": "test",
            "auto_create": False,
        },
    )

    assert isinstance(cfg.config, GaussDBConfig)
    assert VectorStoreFactory.provider_to_class["gaussdb"] == "mem0.vector_stores.gaussdb.GaussDB"


def test_factory_creates_gaussdb_instance():
    db, mock_pool, _, _ = make_gaussdb()
    with patch.object(GaussDB, "_create_connection_pool", return_value=mock_pool):
        with patch.object(GaussDB, "_probe_capabilities"):
            created = VectorStoreFactory.create(
                "gaussdb",
                {
                    "collection_name": "test_collection",
                    "embedding_model_dims": 3,
                    "auto_create": False,
                    "host": "localhost",
                    "port": 5432,
                    "user": "test",
                    "password": "test",
                },
            )

    assert isinstance(created, GaussDB)
    assert created.collection_name == db.collection_name


# ============================================================
# Init validation tests
# ============================================================


def test_rejects_unsafe_identifier():
    with pytest.raises(ValueError, match="Unsafe collection_name"):
        make_gaussdb(collection_name='bad";drop')


def test_distributed_mode_sets_hash_distribution():
    db, _, _, _ = make_gaussdb(deployment_mode="distributed")
    assert db.deployment_mode == "distributed"
    assert db.distribution_mode == "hash"


def test_centralized_mode_sets_none_distribution():
    db, _, _, _ = make_gaussdb(deployment_mode="centralized")
    assert db.deployment_mode == "centralized"
    assert db.distribution_mode == "none"


def test_rejects_high_dims_for_distributed():
    with pytest.raises(ValueError, match="distributed mode supports"):
        make_gaussdb(deployment_mode="distributed", embedding_model_dims=2048)


def test_rejects_high_dims_with_gsivfflat():
    with pytest.raises(ValueError, match="only GsDiskANN supports"):
        make_gaussdb(vector_index_type="gsivfflat", embedding_model_dims=2048)


# ============================================================
# DDL / create_col tests
# ============================================================


def test_create_col_generates_ustore_vector_bm25_and_filter_indexes():
    db, _, mock_conn, mock_cursor = make_gaussdb()

    db.create_col()

    sql = executed_sql(mock_cursor)
    assert "WITH (storage_type=ustore)" in sql
    assert "FLOATVECTOR(3)" in sql
    assert "user_id VARCHAR(128)" in sql
    assert "agent_id VARCHAR(128)" in sql
    assert "run_id VARCHAR(128)" in sql
    assert "SET LOCAL maintenance_work_mem" in sql
    assert "USING gsdiskann (vector COSINE)" in sql
    assert "USING bm25 (text_lemmatized)" in sql
    assert "storage_type='USTORE'" in sql
    assert '("user_id")' in sql or "user_id)" in sql
    mock_cursor.execute.assert_any_call("SET LOCAL maintenance_work_mem = %s", ("128MB",))
    mock_conn.commit.assert_called()


def test_create_col_does_not_accept_alternate_collection_name():
    db, _, _, _ = make_gaussdb()

    with pytest.raises(TypeError):
        db.create_col(name="other_collection")

    with pytest.raises(TypeError):
        db.create_col("other_collection")


def test_distributed_create_col_generates_hash_distribution_clauses():
    db, _, _, mock_cursor = make_gaussdb(deployment_mode="distributed")

    db.create_col()

    sql = executed_sql(mock_cursor)
    assert db.deployment_mode == "distributed"
    assert db.distribution_mode == "hash"
    assert 'DISTRIBUTE BY HASH ("id")' in sql
    assert 'DISTRIBUTE BY HASH ("collection_name")' in sql


# ============================================================
# Capability probe tests
# ============================================================


def test_capability_probe_sets_vector_index_maintenance_work_mem():
    db, _, _, mock_cursor = make_gaussdb()
    mock_cursor.fetchone.return_value = ("on",)

    db._probe_capabilities()

    sql = executed_sql(mock_cursor)
    assert "SHOW enable_vectordb" in sql
    assert "CREATE INDEX" in sql
    assert "INSERT INTO" in sql
    assert "text_lemmatized ### %s AS score" in sql
    mock_cursor.execute.assert_any_call("SET LOCAL maintenance_work_mem = %s", ("128MB",))


def test_set_vector_index_maintenance_work_mem_skips_when_current_is_higher():
    db, _, _, mock_cursor = make_gaussdb()
    mock_cursor.fetchone.return_value = ("4GB",)

    db._set_vector_index_maintenance_work_mem(mock_cursor)

    sql = executed_sql(mock_cursor)
    assert "SHOW maintenance_work_mem" in sql
    assert "SET LOCAL maintenance_work_mem" not in sql


def test_set_vector_index_maintenance_work_mem_raises_default_for_high_dim_gsdiskann():
    db, _, _, mock_cursor = make_gaussdb(embedding_model_dims=2048)
    mock_cursor.fetchone.return_value = ("1GB",)

    db._set_vector_index_maintenance_work_mem(mock_cursor)

    mock_cursor.execute.assert_any_call("SHOW maintenance_work_mem")
    mock_cursor.execute.assert_any_call("SET LOCAL maintenance_work_mem = %s", ("2GB",))


def test_capability_probe_uses_distributed_probe_table_suffix():
    db, _, _, mock_cursor = make_gaussdb(deployment_mode="distributed")
    mock_cursor.fetchone.return_value = ("on",)

    db._probe_capabilities()

    sql = executed_sql(mock_cursor)
    assert 'DISTRIBUTE BY HASH ("id")' in sql


def test_capability_probe_raises_on_jsonb_failure():
    db, _, _, mock_cursor = make_gaussdb()
    mock_cursor.fetchone.return_value = ("on",)

    def execute_side_effect(sql, *args):
        if "CREATE TABLE" in str(sql) and "payload JSONB" in str(sql):
            raise Exception("jsonb type unsupported")

    mock_cursor.execute.side_effect = execute_side_effect

    with pytest.raises(Exception, match="jsonb type unsupported"):
        db._probe_capabilities()


def test_capability_probe_keeps_json_filters_on_expression_index_failure(caplog):
    db, _, _, mock_cursor = make_gaussdb()
    mock_cursor.fetchone.return_value = ("on",)
    caplog.set_level(logging.WARNING, logger="mem0.vector_stores.gaussdb")

    def execute_side_effect(sql, *args):
        if "payload->>'user_id'" in str(sql):
            raise Exception("expression index unsupported")

    mock_cursor.execute.side_effect = execute_side_effect

    db._probe_capabilities()

    assert db.payload_storage_mode == "jsonb"
    assert db.filter_storage_mode == "json_expression"
    assert db.metadata_column_mode == "jsonb"
    assert db.capabilities.expression_index is False
    assert "metadata filters remain available without expression indexes" in caplog.text


def test_filter_index_creation_failure_warns_and_keeps_filter_mode(caplog):
    db, _, _, mock_cursor = make_gaussdb()
    caplog.set_level(logging.WARNING, logger="mem0.vector_stores.gaussdb")

    def execute_side_effect(sql, *args):
        if "CREATE INDEX IF NOT EXISTS" in str(sql) and "user_id" in str(sql):
            raise Exception("expression index unsupported")

    mock_cursor.execute.side_effect = execute_side_effect

    db._create_filter_indexes(mock_cursor, '"public"."test_collection"')

    assert db.filter_storage_mode == "json_expression"
    assert db.metrics.get("gaussdb_fallback_count") == 1
    assert "Filter index creation failed for key user_id" in caplog.text


def test_capability_probe_bm25_score_failure_disables_bm25():
    db, _, _, mock_cursor = make_gaussdb()
    mock_cursor.fetchone.return_value = ("on",)

    def execute_side_effect(sql, *args):
        if "SELECT text_lemmatized ###" in str(sql):
            raise Exception("operator ### unsupported")

    mock_cursor.execute.side_effect = execute_side_effect

    db._probe_capabilities()

    sql = executed_sql(mock_cursor)
    assert "ROLLBACK TO SAVEPOINT" in sql
    assert db.bm25_enabled is False
    assert db.metrics["gaussdb_fallback_count"] == 1


# ============================================================
# BM25 index graceful degradation
# ============================================================


def test_bm25_index_failure_rolls_back_and_disables_bm25():
    db, _, _, mock_cursor = make_gaussdb()
    mock_cursor.execute.side_effect = [None, Exception("bm25 unsupported"), None, None]

    db._create_bm25_index(mock_cursor, '"test_collection"')

    sql = executed_sql(mock_cursor)
    assert "SAVEPOINT" in sql
    assert "ROLLBACK TO SAVEPOINT" in sql
    assert "RELEASE SAVEPOINT" in sql
    assert db.bm25_enabled is False
    assert db.metrics["gaussdb_fallback_count"] == 1


def test_create_col_keeps_collection_when_bm25_index_fails():
    db, _, mock_conn, mock_cursor = make_gaussdb()

    def execute_side_effect(sql, *args):
        if "USING bm25" in str(sql):
            raise Exception("bm25 unsupported")

    mock_cursor.execute.side_effect = execute_side_effect

    db.create_col()

    sql = executed_sql(mock_cursor)
    assert "CREATE TABLE IF NOT EXISTS" in sql
    assert "USING gsdiskann (vector COSINE)" in sql
    assert "USING bm25 (text_lemmatized)" in sql
    assert "ROLLBACK TO SAVEPOINT" in sql
    assert '"user_id"' in sql
    assert db.bm25_enabled is False
    assert db.metrics["gaussdb_fallback_count"] == 1
    mock_conn.commit.assert_called()


# ============================================================
# Insert tests
# ============================================================


def test_insert_uses_merge_into_and_vector_cast():
    db, _, _, mock_cursor = make_gaussdb()

    db.insert(
        vectors=[[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]],
        payloads=[
            {"data": "hello", "text_lemmatized": "hello", "user_id": "u1"},
            {"data": "world", "text_lemmatized": "world", "user_id": "u1"},
        ],
        ids=["11111111-1111-1111-1111-111111111111", "22222222-2222-2222-2222-222222222222"],
    )

    sql = executed_sql(mock_cursor)
    merge_args = mock_cursor.execute.call_args_list[-1].args[1]
    assert "MERGE INTO" in sql
    assert "WHEN MATCHED THEN" in sql
    assert "WHEN NOT MATCHED THEN" in sql
    assert mock_cursor.execute.call_count == 1
    assert "%s::FLOATVECTOR" in sql
    assert merge_args[1] == "[0.1,0.2,0.3]"
    assert merge_args[3] == "hello"
    assert merge_args[6] == "u1"


def test_insert_many_rows_uses_single_merge_statement():
    db, _, _, mock_cursor = make_gaussdb()

    db.insert(
        vectors=[[0.1, 0.2, 0.3], [0.4, 0.5, 0.6], [0.7, 0.8, 0.9]],
        payloads=[
            {"data": "a", "text_lemmatized": "a", "user_id": "u1"},
            {"data": "b", "text_lemmatized": "b", "user_id": "u1"},
            {"data": "c", "text_lemmatized": "c", "user_id": "u1"},
        ],
        ids=[
            "11111111-1111-1111-1111-111111111111",
            "22222222-2222-2222-2222-222222222222",
            "33333333-3333-3333-3333-333333333333",
        ],
    )

    calls = mock_cursor.execute.call_args_list
    assert len(calls) == 1
    assert "MERGE INTO" in str(calls[0].args[0])
    assert len(calls[0].args[1]) == 27


def test_insert_raises_on_mismatched_lengths():
    db, _, _, _ = make_gaussdb()

    with pytest.raises(ValueError, match="same length"):
        db.insert(vectors=[[0.1, 0.2, 0.3]], payloads=[{"a": 1}, {"b": 2}])

    with pytest.raises(ValueError, match="same length"):
        db.insert(vectors=[[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]], ids=["id1"])

    with pytest.raises(ValueError, match="same length"):
        db.insert(vectors=[[0.1, 0.2, 0.3]], payloads=[], ids=["id1"])

    with pytest.raises(ValueError, match="same length"):
        db.insert(vectors=[[0.1, 0.2, 0.3]], payloads=[{}], ids=[])


def test_insert_none_payloads_and_ids_use_defaults():
    db, _, _, mock_cursor = make_gaussdb()

    db.insert(vectors=[[0.1, 0.2, 0.3]], payloads=None, ids=None)

    sql = executed_sql(mock_cursor)
    params = mock_cursor.execute.call_args.args[1]
    assert "MERGE INTO" in sql
    assert params[1] == "[0.1,0.2,0.3]"
    assert params[3] is None


# ============================================================
# Search tests
# ============================================================


def test_search_uses_cosine_operator_and_raw_distance_score():
    db, _, _, mock_cursor = make_gaussdb()
    mock_cursor.fetchall.return_value = [("id1", 0.25, {"data": "hello", "user_id": "u1"})]

    results = db.search("hello", [0.1, 0.2, 0.3], top_k=5, filters={"user_id": "u1"})

    sql = executed_sql(mock_cursor)
    assert "vector <+> %s::FLOATVECTOR AS distance" in sql
    assert '"user_id" = %s' in sql
    assert results[0].id == "id1"
    assert results[0].score == pytest.approx(0.25)
    assert results[0].payload["data"] == "hello"


def test_search_typed_bool_filter_uses_jsonb_containment():
    db, _, _, mock_cursor = make_gaussdb()
    mock_cursor.fetchall.return_value = [("id1", 0.1, {"data": "hello", "flag": True, "user_id": "u1"})]

    results = db.search("hello", [0.1, 0.2, 0.3], filters={"user_id": "u1", "flag": True})

    sql = executed_sql(mock_cursor)
    params = mock_cursor.execute.call_args.args[1]
    assert "payload @> %s::JSONB" in sql
    assert '"user_id" = %s' in sql
    assert params[1] == "u1"
    assert params[2] == '{"flag":true}'
    assert results[0].id == "id1"


def test_search_wildcard_filter_is_skipped_not_literal_match():
    db, _, _, mock_cursor = make_gaussdb()
    mock_cursor.fetchall.return_value = []

    db.search("hello", [0.1, 0.2, 0.3], filters={"user_id": "u1", "category": "*"})

    sql = executed_sql(mock_cursor)
    params = mock_cursor.execute.call_args.args[1]
    assert "category" not in sql
    assert params == ("[0.1,0.2,0.3]", "u1", 5)


def test_search_all_wildcard_metadata_filters_do_not_leave_dangling_and():
    db, _, _, mock_cursor = make_gaussdb(require_scoped_filters=False)
    mock_cursor.fetchall.return_value = []

    db.search("hello", [0.1, 0.2, 0.3], filters={"category": "*", "tag": "*"})

    sql = executed_sql(mock_cursor)
    assert "WHERE" not in sql or "WHERE  ORDER" not in sql
    assert "AND  ORDER" not in sql
    assert "category" not in sql
    assert "tag" not in sql


def test_search_eq_null_uses_jsonb_null_containment():
    db, _, _, mock_cursor = make_gaussdb()
    mock_cursor.fetchall.return_value = []

    db.search("hello", [0.1, 0.2, 0.3], filters={"user_id": "u1", "deleted_at": None})

    sql = executed_sql(mock_cursor)
    params = mock_cursor.execute.call_args.args[1]
    assert "payload @> %s::JSONB" in sql
    assert params[2] == '{"deleted_at":null}'


def test_search_ne_bool_uses_typed_jsonb_negation():
    db, _, _, mock_cursor = make_gaussdb()
    mock_cursor.fetchall.return_value = []

    db.search("hello", [0.1, 0.2, 0.3], filters={"user_id": "u1", "flag": {"ne": True}})

    sql = executed_sql(mock_cursor)
    params = mock_cursor.execute.call_args.args[1]
    assert "(payload @> %s::JSONB) IS NOT TRUE" in sql
    assert params[2] == '{"flag":true}'


def test_search_exists_filter_uses_jsonb_key_presence():
    db, _, _, mock_cursor = make_gaussdb()
    mock_cursor.fetchall.return_value = []

    db.search("hello", [0.1, 0.2, 0.3], filters={"user_id": "u1", "flag": {"exists": True}})

    sql = executed_sql(mock_cursor)
    params = mock_cursor.execute.call_args.args[1]
    assert "payload ? %s" in sql
    assert params[2] == "flag"


def test_search_missing_filter_uses_jsonb_key_absence():
    db, _, _, mock_cursor = make_gaussdb()
    mock_cursor.fetchall.return_value = []

    db.search("hello", [0.1, 0.2, 0.3], filters={"user_id": "u1", "flag": {"missing": True}})

    sql = executed_sql(mock_cursor)
    params = mock_cursor.execute.call_args.args[1]
    assert "(payload ? %s) IS NOT TRUE" in sql
    assert params[2] == "flag"


def test_search_exists_false_aliases_to_missing():
    db, _, _, mock_cursor = make_gaussdb()
    mock_cursor.fetchall.return_value = []

    db.search("hello", [0.1, 0.2, 0.3], filters={"user_id": "u1", "flag": {"exists": False}})

    sql = executed_sql(mock_cursor)
    params = mock_cursor.execute.call_args.args[1]
    assert "(payload ? %s) IS NOT TRUE" in sql
    assert params[2] == "flag"


def test_search_presence_filter_rejects_non_boolean_flag():
    db, _, _, _ = make_gaussdb()

    with pytest.raises(ValueError, match="must be a boolean"):
        db.search("hello", [0.1, 0.2, 0.3], filters={"user_id": "u1", "flag": {"exists": "yes"}})


def test_search_presence_filter_requires_single_operator():
    db, _, _, _ = make_gaussdb()

    with pytest.raises(ValueError, match="exactly one"):
        db.search("hello", [0.1, 0.2, 0.3], filters={"user_id": "u1", "flag": {"exists": True, "missing": True}})


def test_search_not_uses_is_not_true_semantics():
    db, _, _, mock_cursor = make_gaussdb()
    mock_cursor.fetchall.return_value = []

    db.search("hello", [0.1, 0.2, 0.3], filters={"user_id": "u1", "$not": [{"category": "food"}]})

    sql = executed_sql(mock_cursor)
    assert "((payload @> %s::JSONB) IS NOT TRUE)" in sql


def test_search_range_on_undeclared_field_warns_and_falls_back_to_literal_match(caplog):
    db, _, _, mock_cursor = make_gaussdb()
    mock_cursor.fetchall.return_value = []
    caplog.set_level(logging.WARNING, logger="mem0.vector_stores.gaussdb")

    db.search("hello", [0.1, 0.2, 0.3], filters={"user_id": "u1", "priority": {"gte": 3}})

    sql = executed_sql(mock_cursor)
    params = mock_cursor.execute.call_args.args[1]
    assert "payload @> %s::JSONB" in sql
    assert params[2] == '{"priority":{"gte":3}}'
    assert "falling back to literal compatibility matching" in caplog.text


def test_search_declared_numeric_range_uses_typed_numeric_cast():
    db, _, _, mock_cursor = make_gaussdb()
    db.metadata_schema = {"priority": "number"}
    mock_cursor.fetchall.return_value = []

    db.search("hello", [0.1, 0.2, 0.3], filters={"user_id": "u1", "priority": {"gte": 3, "lt": 7}})

    sql = executed_sql(mock_cursor)
    params = mock_cursor.execute.call_args.args[1]
    assert "CASE WHEN jsonb_typeof(payload->'priority') = 'number'" in sql
    assert "THEN CAST(payload->>'priority' AS DOUBLE PRECISION) END >= %s" in sql
    assert "THEN CAST(payload->>'priority' AS DOUBLE PRECISION) END < %s" in sql
    assert params[1] == "u1"
    assert params[2] == 3
    assert params[3] == 7


def test_list_declared_datetime_range_uses_timestamptz_cast_and_guard():
    db, _, _, mock_cursor = make_gaussdb()
    db.require_scoped_filters = False
    db.metadata_schema = {"created_at": "datetime"}
    mock_cursor.fetchall.return_value = []

    db.list(filters={"created_at": {"lt": "2026-01-01T00:00:00Z"}})

    sql = executed_sql(mock_cursor)
    params = mock_cursor.execute.call_args.args[1]
    assert "CASE WHEN jsonb_typeof(payload->'created_at') = 'string'" in sql
    assert "payload->>'created_at' ~ %s" in sql
    assert "THEN CAST(payload->>'created_at' AS TIMESTAMPTZ) END < %s" in sql
    assert params[0].startswith("^\\d{4}-\\d{2}-\\d{2}T")
    assert params[1] == "2026-01-01T00:00:00Z"
    assert params[2] == 100


def test_list_declared_datetime_range_with_multiple_bounds_repeats_regex_params():
    db, _, _, mock_cursor = make_gaussdb()
    db.require_scoped_filters = False
    db.metadata_schema = {"created_at": "datetime"}
    mock_cursor.fetchall.return_value = []

    db.list(
        filters={
            "created_at": {
                "gte": "2026-01-01T00:00:00Z",
                "lt": "2026-12-31T00:00:00Z",
            }
        }
    )

    sql = executed_sql(mock_cursor)
    params = mock_cursor.execute.call_args.args[1]
    assert sql.count("payload->>'created_at' ~ %s") == 2
    assert params[0].startswith("^\\d{4}-\\d{2}-\\d{2}T")
    assert params[1] == "2026-01-01T00:00:00Z"
    assert params[2].startswith("^\\d{4}-\\d{2}-\\d{2}T")
    assert params[3] == "2026-12-31T00:00:00Z"
    assert params[4] == 100


def test_range_on_non_range_declared_type_warns_and_falls_back(caplog):
    db, _, _, mock_cursor = make_gaussdb()
    db.metadata_schema = {"category": "string"}
    mock_cursor.fetchall.return_value = []
    caplog.set_level(logging.WARNING, logger="mem0.vector_stores.gaussdb")

    db.search("hello", [0.1, 0.2, 0.3], filters={"user_id": "u1", "category": {"gte": "a"}})

    sql = executed_sql(mock_cursor)
    params = mock_cursor.execute.call_args.args[1]
    assert "payload @> %s::JSONB" in sql
    assert params[2] == '{"category":{"gte":"a"}}'
    assert "falling back to literal compatibility matching" in caplog.text


def test_search_requires_scoped_filters_when_explicitly_enabled():
    db, _, _, _ = make_gaussdb(require_scoped_filters=True)

    with pytest.raises(ValueError, match="requires at least one scoped filter"):
        db.search("hello", [0.1, 0.2, 0.3], filters={"category": "test"})


def test_constructor_allows_unscoped_reads_by_default():
    db, _, _, mock_cursor = make_gaussdb(require_scoped_filters=False)
    mock_cursor.fetchall.return_value = []

    assert db.require_scoped_filters is False
    assert db.search("hello", [0.1, 0.2, 0.3], filters={"category": "test"}) == []


def test_constructor_warns_when_server_encoding_is_not_utf8(caplog):
    caplog.set_level(logging.WARNING, logger="mem0.vector_stores.gaussdb")
    db, _, mock_conn, _ = make_gaussdb()
    mock_conn.get_parameter_status.return_value = "SQL_ASCII"

    db._warn_if_server_encoding_is_not_utf8()

    assert "designed and validated for UTF8 databases" in caplog.text
    assert "server_encoding=SQL_ASCII" in caplog.text


def test_constructor_does_not_warn_when_server_encoding_is_utf8(caplog):
    caplog.set_level(logging.WARNING, logger="mem0.vector_stores.gaussdb")
    db, _, mock_conn, _ = make_gaussdb()
    mock_conn.get_parameter_status.return_value = "UTF8"

    db._warn_if_server_encoding_is_not_utf8()

    assert "server_encoding" not in caplog.text


def test_constructor_accepts_metadata_schema():
    db, _, _, _ = make_gaussdb(metadata_schema={"priority": "number", "created_at": "datetime"})

    assert db.metadata_schema == {"priority": "number", "created_at": "datetime"}


def test_constructor_accepts_custom_schema_and_uses_qualified_names():
    db, _, _, _ = make_gaussdb(schema="mem0_app")

    assert db.schema == "mem0_app"
    assert db.table_name == '"mem0_app"."test_collection"'
    assert db.schema_meta_table_name == '"mem0_app"."test_collection_schema_meta"'


@pytest.mark.parametrize(
    "filters",
    [
        {"OR": [{"user_id": "alice"}, {"category": "public"}]},
        {"$or": [{"user_id": "alice"}, {"category": "public"}]},
        {"NOT": [{"user_id": "alice"}]},
        {"user_id": {"ne": "alice"}},
        {"user_id": {"nin": ["alice"]}},
        {"user_id": "*"},
        {"user_id": {"exists": True}},
        {"user_id": {"missing": True}},
    ],
)
def test_search_rejects_non_constraining_scope_filters(filters):
    db, _, _, _ = make_gaussdb(require_scoped_filters=True)

    with pytest.raises(ValueError, match="requires at least one scoped filter"):
        db.search("hello", [0.1, 0.2, 0.3], filters=filters)


@pytest.mark.parametrize(
    "filters",
    [
        {"user_id": "alice"},
        {"user_id": {"eq": "alice"}},
        {"user_id": {"in": ["alice", "bob"]}},
        {"AND": [{"category": "travel"}, {"user_id": "alice"}]},
        {"$and": [{"category": "travel"}, {"user_id": {"eq": "alice"}}]},
        {"OR": [{"user_id": "alice"}, {"user_id": "bob"}]},
        {"$or": [{"user_id": {"eq": "alice"}}, {"agent_id": {"in": ["agent-1", "agent-2"]}}]},
        {"AND": [{"category": "travel"}, {"OR": [{"user_id": "alice"}, {"run_id": "run-1"}]}]},
    ],
)
def test_search_accepts_positive_constraining_scope_filters(filters):
    db, _, _, mock_cursor = make_gaussdb()
    mock_cursor.fetchall.return_value = []

    assert db.search("hello", [0.1, 0.2, 0.3], filters=filters) == []
    assert mock_cursor.execute.called


def test_filter_builder_rejects_unsafe_keys():
    db, _, _, _ = make_gaussdb()
    db.require_scoped_filters = False

    with pytest.raises(ValueError, match="Unsafe filter key"):
        db.list(filters={"bad-key": "x"})


def test_list_uses_scope_columns_and_typed_bool_filters():
    db, _, _, mock_cursor = make_gaussdb()
    db.require_scoped_filters = False
    mock_cursor.fetchall.return_value = []

    db.list(filters={"user_id": "u1", "flag": True})

    sql = executed_sql(mock_cursor)
    params = mock_cursor.execute.call_args.args[1]
    assert '"user_id" = %s' in sql
    assert "payload @> %s::JSONB" in sql
    assert params[0] == "u1"
    assert params[1] == '{"flag":true}'


# ============================================================
# Keyword search tests
# ============================================================


def test_keyword_search_uses_bm25_defaults_and_filters():
    db, _, _, mock_cursor = make_gaussdb()
    mock_cursor.fetchall.return_value = [("id1", 2.5, {"data": "hello", "user_id": "u1"})]

    results = db.keyword_search("hello", top_k=3, filters={"user_id": "u1"})

    sql = executed_sql(mock_cursor)
    assert "SET LOCAL bm25_ranking_metric = 0" in sql
    assert "SET LOCAL bm25_ncandidates = 128" in sql
    assert "SET LOCAL enable_seqscan = off" in sql
    assert "text_lemmatized ### %s AS score" in sql
    assert "ORDER BY score DESC" in sql
    assert results[0].score == 2.5


def test_keyword_search_uses_scope_columns_and_typed_exact_filters():
    db, _, _, mock_cursor = make_gaussdb()
    mock_cursor.fetchall.return_value = []

    db.keyword_search("hello", top_k=3, filters={"user_id": "u1", "flag": True})

    sql = executed_sql(mock_cursor)
    params = mock_cursor.execute.call_args.args[1]
    assert '"user_id" = %s' in sql
    assert "payload @> %s::JSONB" in sql
    assert "hello" in params
    assert "u1" in params
    assert '{"flag":true}' in params


def test_keyword_search_empty_query_returns_empty_list():
    db, _, _, mock_cursor = make_gaussdb()

    assert db.keyword_search(" ", filters={"user_id": "u1"}) == []
    mock_cursor.execute.assert_not_called()


def test_keyword_search_returns_none_when_bm25_disabled():
    db, _, _, _ = make_gaussdb()
    db.bm25_enabled = False

    assert db.keyword_search("hello", filters={"user_id": "u1"}) is None


@pytest.mark.parametrize(
    "filters",
    [
        {"OR": [{"user_id": "alice"}, {"category": "public"}]},
        {"$or": [{"user_id": "alice"}, {"category": "public"}]},
        {"NOT": [{"user_id": "alice"}]},
        {"user_id": {"ne": "alice"}},
        {"user_id": {"nin": ["alice"]}},
    ],
)
def test_keyword_search_rejects_non_constraining_scope_filters(filters):
    db, _, _, mock_cursor = make_gaussdb(require_scoped_filters=True)

    with pytest.raises(ValueError, match="requires at least one scoped filter"):
        db.keyword_search("hello", top_k=3, filters=filters)

    mock_cursor.execute.assert_not_called()


# ============================================================
# Search batch tests
# ============================================================


def test_search_batch_returns_one_result_list_per_query():
    db, _, _, mock_cursor = make_gaussdb()
    mock_cursor.fetchall.side_effect = [
        [("id1", 0.1, {"data": "a", "user_id": "u1"})],
        [("id2", 0.2, {"data": "b", "user_id": "u1"})],
    ]

    results = db.search_batch(
        queries=["a", "b"],
        vectors_list=[[0.1, 0.2, 0.3], [0.3, 0.2, 0.1]],
        filters={"user_id": "u1"},
    )

    assert len(results) == 2
    assert results[0][0].id == "id1"
    assert results[1][0].id == "id2"
    assert mock_cursor.execute.call_count == 2


def test_search_batch_uses_scope_columns_and_typed_exact_filters():
    db, _, _, mock_cursor = make_gaussdb()
    mock_cursor.fetchall.side_effect = [[], []]

    db.search_batch(
        queries=["hello", "world"],
        vectors_list=[[0.1, 0.2, 0.3], [0.3, 0.2, 0.1]],
        filters={"user_id": "u1", "flag": True},
    )

    sql = executed_sql(mock_cursor)
    params = mock_cursor.execute.call_args.args[1]
    assert '"user_id" = %s' in sql
    assert "payload @> %s::JSONB" in sql
    assert params[1] == "u1"
    assert params[2] == '{"flag":true}'


def test_search_batch_uses_sequential_search_path():
    db, _, _, mock_cursor = make_gaussdb()
    mock_cursor.fetchall.side_effect = [
        [("id1", 0.1, {"data": "a", "user_id": "u1"})],
        [("id2", 0.2, {"data": "b", "user_id": "u1"})],
    ]

    results = db.search_batch(
        queries=["a", "b"],
        vectors_list=[[0.1, 0.2, 0.3], [0.3, 0.2, 0.1]],
        filters={"user_id": "u1"},
    )

    assert len(results) == 2
    assert results[0][0].id == "id1"
    assert results[1][0].id == "id2"
    assert db.metrics.get("gaussdb_fallback_count", 0) == 0


@pytest.mark.parametrize(
    "filters",
    [
        {"OR": [{"user_id": "alice"}, {"category": "public"}]},
        {"$or": [{"user_id": "alice"}, {"category": "public"}]},
        {"NOT": [{"user_id": "alice"}]},
        {"user_id": {"ne": "alice"}},
        {"user_id": {"nin": ["alice"]}},
    ],
)
def test_search_batch_rejects_non_constraining_scope_filters(filters):
    db, _, _, mock_cursor = make_gaussdb(require_scoped_filters=True)

    with pytest.raises(ValueError, match="requires at least one scoped filter"):
        db.search_batch(["hello"], [[0.1, 0.2, 0.3]], filters=filters)

    mock_cursor.execute.assert_not_called()


# ============================================================
# Update tests
# ============================================================


def test_update_vector_and_payload_updates_timestamp():
    db, _, _, mock_cursor = make_gaussdb()

    db.update("id1", vector=[0.1, 0.2, 0.3], payload={"data": "new", "text_lemmatized": "new"})

    sql = executed_sql(mock_cursor)
    assert 'UPDATE "public"."test_collection"' in sql
    assert "vector = %s::FLOATVECTOR" in sql
    assert "payload = %s::JSONB" in sql
    assert "updated_at = CURRENT_TIMESTAMP" in sql


def test_update_vector_only_does_not_touch_payload():
    db, _, _, mock_cursor = make_gaussdb()

    db.update("id1", vector=[0.1, 0.2, 0.3])

    sql = executed_sql(mock_cursor)
    params = mock_cursor.execute.call_args.args[1]
    assert "vector = %s::FLOATVECTOR" in sql
    assert "payload = %s" not in sql
    assert "memory = %s" not in sql
    assert params == ("[0.1,0.2,0.3]", "id1")


def test_update_payload_only_refreshes_text_fields():
    db, _, _, mock_cursor = make_gaussdb()

    db.update("id1", payload={"data": "new", "text_lemmatized": "new lemma"})

    sql = executed_sql(mock_cursor)
    params = mock_cursor.execute.call_args.args[1]
    assert "vector = %s::FLOATVECTOR" not in sql
    assert "payload = %s::JSONB" in sql
    assert "memory = %s" in sql
    assert "text_lemmatized = %s" in sql
    assert params[-3:] == ("new", "new lemma", "id1")



# ============================================================
# LIKE escape tests
# ============================================================


def test_contains_filter_escapes_percent_wildcard():
    db, _, _, mock_cursor = make_gaussdb()
    db.require_scoped_filters = False
    mock_cursor.fetchall.return_value = []

    db.list(filters={"user_id": {"contains": "100%"}})

    sql = executed_sql(mock_cursor)
    assert "LIKE %s ESCAPE" in sql
    call_args = mock_cursor.execute.call_args
    params = call_args[0][1] if len(call_args[0]) > 1 else call_args[1].get("params", [])
    assert any("%100\\%%" in str(p) for p in params)


def test_contains_filter_escapes_underscore_wildcard():
    db, _, _, mock_cursor = make_gaussdb()
    db.require_scoped_filters = False
    mock_cursor.fetchall.return_value = []

    db.list(filters={"user_id": {"contains": "a_b"}})

    call_args = mock_cursor.execute.call_args
    params = call_args[0][1] if len(call_args[0]) > 1 else call_args[1].get("params", [])
    assert any("%a\\_b%" in str(p) for p in params)


def test_icontains_filter_escapes_backslash():
    db, _, _, mock_cursor = make_gaussdb()
    db.require_scoped_filters = False
    mock_cursor.fetchall.return_value = []

    db.list(filters={"user_id": {"icontains": r"a\b"}})

    sql = executed_sql(mock_cursor)
    assert "LOWER" in sql
    assert "ESCAPE" in sql
    call_args = mock_cursor.execute.call_args
    params = call_args[0][1] if len(call_args[0]) > 1 else call_args[1].get("params", [])
    assert any(r"%a\\b%" in str(p) for p in params)


@pytest.mark.parametrize("op", ["gt", "gte", "lt", "lte"])
def test_range_filter_operator_dict_warns_and_falls_back_without_declared_type(op, caplog):
    db, _, _, mock_cursor = make_gaussdb()
    db.require_scoped_filters = False
    mock_cursor.fetchall.return_value = []
    caplog.set_level(logging.WARNING, logger="mem0.vector_stores.gaussdb")

    db.list(filters={"priority": {op: 2}})

    sql = executed_sql(mock_cursor)
    params = mock_cursor.execute.call_args.args[1]
    assert "payload @> %s::JSONB" in sql
    assert params[0] == json.dumps({"priority": {op: 2}}, ensure_ascii=False, separators=(",", ":"))
    assert "falling back to literal compatibility matching" in caplog.text


# ============================================================
# Transaction rollback test
# ============================================================


def test_transaction_rollback_on_error():
    db, _, mock_conn, mock_cursor = make_gaussdb()
    mock_cursor.execute.side_effect = Exception("Database error")

    with pytest.raises(Exception, match="Database error"):
        db.delete("id1")

    mock_conn.rollback.assert_called()


# ============================================================
# _upsert_schema_meta uses MERGE INTO
# ============================================================


def test_upsert_schema_meta_uses_merge_into():
    db, _, _, mock_cursor = make_gaussdb()

    db._upsert_schema_meta(mock_cursor, "test_collection", 3)

    sql = executed_sql(mock_cursor)
    assert "MERGE INTO" in sql
    assert "WHEN MATCHED THEN" in sql
    assert "WHEN NOT MATCHED THEN" in sql


def test_upsert_schema_meta_passes_correct_params():
    db, _, _, mock_cursor = make_gaussdb()

    db._upsert_schema_meta(mock_cursor, "my_collection", 5)

    call_args = mock_cursor.execute.call_args
    params = call_args[0][1]
    assert params == ("my_collection", 5)



# ============================================================
# Delete / List / Col info tests
# ============================================================


def test_delete_is_idempotent_sql_path():
    db, _, mock_conn, mock_cursor = make_gaussdb()

    db.delete("id1")

    sql = executed_sql(mock_cursor)
    assert 'DELETE FROM "public"."test_collection" WHERE id = %s' in sql
    mock_conn.commit.assert_called()


def test_list_returns_wrapped_results():
    db, _, _, mock_cursor = make_gaussdb()
    mock_cursor.fetchall.return_value = [("id1", {"data": "hello", "user_id": "u1"})]

    results = db.list(filters={"user_id": "u1"})

    assert isinstance(results, list)
    assert isinstance(results[0], list)
    assert results[0][0].id == "id1"


def test_list_top_k_zero_is_preserved():
    db, _, _, mock_cursor = make_gaussdb()
    mock_cursor.fetchall.return_value = []

    db.list(filters={"user_id": "u1"}, top_k=0)

    assert mock_cursor.execute.call_args.args[1][-1] == 0


def test_col_info_reads_schema_version():
    db, _, _, mock_cursor = make_gaussdb()
    mock_cursor.fetchone.side_effect = [(3,), (True,), (7,)]
    mock_cursor.fetchall.return_value = [("test_collection_vector_idx",), ("test_collection_bm25_idx",)]

    info = db.col_info()

    sql = executed_sql(mock_cursor)
    assert "information_schema.tables" in sql
    assert info["count"] == 3
    assert info["schema_version"] == 7
    assert info["deployment_mode"] == "centralized"
    assert info["distribution_mode"] == "none"
    assert info["indexes"] == ["test_collection_vector_idx", "test_collection_bm25_idx"]


def test_col_info_defaults_schema_version_when_meta_table_missing():
    db, _, _, mock_cursor = make_gaussdb()
    mock_cursor.fetchone.side_effect = [(3,), (False,)]
    mock_cursor.fetchall.return_value = []

    info = db.col_info()

    assert info["schema_version"] == 1


# ============================================================
# Close / context manager tests
# ============================================================


def test_close_calls_closeall_and_nullifies_pool():
    db, mock_pool, _, _ = make_gaussdb()

    db.close()

    mock_pool.closeall.assert_called_once()
    assert db.connection_pool is None


def test_close_swallows_exception_from_closeall():
    db, mock_pool, _, _ = make_gaussdb()
    mock_pool.closeall.side_effect = RuntimeError("pool error")

    db.close()

    assert db.connection_pool is None


def test_close_is_idempotent():
    db, _, _, _ = make_gaussdb()

    db.close()
    db.close()


def test_context_manager_calls_close_on_normal_exit():
    db, mock_pool, _, _ = make_gaussdb()

    with db:
        pass

    mock_pool.closeall.assert_called_once()
    assert db.connection_pool is None


def test_context_manager_calls_close_on_exception():
    db, mock_pool, _, _ = make_gaussdb()

    with pytest.raises(ValueError):
        with db:
            raise ValueError("boom")

    mock_pool.closeall.assert_called_once()
    assert db.connection_pool is None


# ============================================================
# Retry logic tests
# ============================================================


def test_retryable_error_triggers_retry_and_succeeds():
    db, _, _, mock_cursor = make_gaussdb()
    call_count = {"n": 0}

    def side_effect(sql, *args, **kwargs):
        call_count["n"] += 1
        if call_count["n"] == 1 and "DELETE" in str(sql):
            raise Exception("connection reset by peer")
        return None

    mock_cursor.execute.side_effect = side_effect

    db.delete("id1")

    assert call_count["n"] >= 2


def test_non_retryable_error_raises_immediately():
    db, _, _, mock_cursor = make_gaussdb()
    mock_cursor.execute.side_effect = Exception("syntax error at position 42")

    with pytest.raises(Exception, match="syntax error"):
        db.delete("id1")

    assert mock_cursor.execute.call_count == 1


def test_retry_exhaustion_raises_last_error():
    db, _, _, mock_cursor = make_gaussdb()
    mock_cursor.execute.side_effect = Exception("connection timeout")

    with pytest.raises(Exception, match="connection timeout"):
        db.delete("id1")


def test_is_retryable_classifies_known_fragments():
    assert GaussDB._is_retryable(Exception("connection reset")) is True
    assert GaussDB._is_retryable(Exception("timeout expired")) is True
    assert GaussDB._is_retryable(Exception("deadlock detected")) is True
    assert GaussDB._is_retryable(Exception("lock wait timeout")) is True
    assert GaussDB._is_retryable(Exception("could not serialize access")) is True
    assert GaussDB._is_retryable(Exception("server closed the connection")) is True
    assert GaussDB._is_retryable(Exception("terminating connection")) is True
    assert GaussDB._is_retryable(Exception("syntax error")) is False
    assert GaussDB._is_retryable(Exception("unique violation")) is False


# ============================================================
# Additional helper / edge coverage
# ============================================================


def test_first_env_returns_first_non_empty(monkeypatch):
    monkeypatch.delenv("GAUSS_A", raising=False)
    monkeypatch.setenv("GAUSS_B", "value-b")
    monkeypatch.setenv("GAUSS_C", "value-c")

    assert gaussdb_module._first_env("GAUSS_A", "GAUSS_B", "GAUSS_C") == "value-b"
    assert gaussdb_module._first_env("GAUSS_X", "GAUSS_Y") is None


def test_enable_bm25_alias_property_round_trips():
    db, *_ = make_gaussdb()

    db.enable_bm25 = False
    assert db.enable_bm25 is False
    assert db.bm25_enabled is False

    db.enable_bm25 = True
    assert db.enable_bm25 is True
    assert db.bm25_enabled is True


def test_validate_positive_int_and_choice_reject_invalid_values():
    with pytest.raises(ValueError):
        GaussDB._validate_positive_int(0, "minconn")
    with pytest.raises(ValueError):
        GaussDB._validate_choice("bad", "vector_metric", {"cosine", "l2"})


def test_warn_if_server_encoding_reads_parameter_status_and_warns(caplog):
    db, mock_pool, mock_conn, mock_cursor = make_gaussdb()
    mock_conn.get_parameter_status.return_value = "SQL_ASCII"

    with caplog.at_level(logging.WARNING):
        db._warn_if_server_encoding_is_not_utf8()

    assert "server_encoding=SQL_ASCII" in caplog.text
    mock_pool.putconn.assert_called_with(mock_conn)
    mock_cursor.execute.assert_not_called()


def test_warn_if_server_encoding_falls_back_to_show_and_handles_unknown(caplog):
    db, mock_pool, mock_conn, mock_cursor = make_gaussdb()
    mock_conn.get_parameter_status.return_value = None
    mock_cursor.fetchone.return_value = (None,)

    with caplog.at_level(logging.WARNING):
        db._warn_if_server_encoding_is_not_utf8()

    assert "Unable to determine GaussDB server_encoding" in caplog.text
    assert "SHOW server_encoding" in executed_sql(mock_cursor)
    mock_pool.putconn.assert_called_with(mock_conn)


def test_warn_if_server_encoding_handles_probe_exception(caplog):
    db, mock_pool, mock_conn, mock_cursor = make_gaussdb()
    mock_conn.get_parameter_status.side_effect = RuntimeError("boom")

    with caplog.at_level(logging.WARNING):
        db._warn_if_server_encoding_is_not_utf8()

    assert "Unable to verify GaussDB server_encoding" in caplog.text
    mock_conn.rollback.assert_called()
    mock_pool.putconn.assert_called_with(mock_conn)


def test_warn_if_server_encoding_always_returns_connection_on_late_warning_path(caplog):
    db, mock_pool, mock_conn, mock_cursor = make_gaussdb()
    mock_conn.get_parameter_status.return_value = None
    mock_cursor.fetchone.return_value = ("SQL_ASCII",)

    with caplog.at_level(logging.WARNING):
        db._warn_if_server_encoding_is_not_utf8()

    assert "server_encoding=SQL_ASCII" in caplog.text
    mock_pool.putconn.assert_called_with(mock_conn)


def test_index_name_hashes_when_too_long():
    name = GaussDB._index_name("a" * 70, "vector_idx")

    assert len(name) <= 63
    assert name.endswith("_vector_idx")


def test_validate_filter_key_rejects_unsafe_and_unsupported_keys():
    db, *_ = make_gaussdb()
    db.allowed_filter_keys = {"safe_key"}

    with pytest.raises(ValueError):
        db._validate_filter_key("bad-key")
    with pytest.raises(ValueError):
        db._validate_filter_key("other_key")


def test_create_connection_pool_requires_driver_package():
    db, *_ = make_gaussdb()
    with patch.object(gaussdb_module, "ThreadedConnectionPool", None):
        with pytest.raises(ImportError):
            db._create_connection_pool()


def test_build_dsn_uses_connection_string_and_appends_ssl():
    db, *_ = make_gaussdb(
        connection_string="postgresql://user:pass@localhost:19995/mem0db",
        sslmode="require",
        sslrootcert="/tmp/root.crt",
    )

    dsn = db._build_dsn()
    assert "sslmode=require" in dsn
    assert "sslrootcert=/tmp/root.crt" in dsn


def test_build_dsn_requires_individual_fields_when_missing():
    db, *_ = make_gaussdb(connection_string=None, user=None, host=None, password=None, port=None)
    with pytest.raises(ValueError):
        db._build_dsn()


def test_build_dsn_quotes_individual_values_with_whitespace():
    db, *_ = make_gaussdb(
        connection_string=None,
        user="user",
        password="p ass'word",
        host="db host",
        port=19995,
        sslmode="verify-full",
        sslrootcert="C:\\root cert.pem",
    )

    dsn = db._build_dsn()
    assert "dbname=postgres" in dsn
    assert "password='p ass\\'word'" in dsn
    assert "host='db host'" in dsn
    assert "sslrootcert='C:\\\\root cert.pem'" in dsn


def test_sanitize_dsn_redacts_passwords():
    dsn = "dbname=postgres user=a password='secret pass' host=localhost"
    url = "postgresql://user:secret@localhost:5432/db"

    assert "<redacted>" in GaussDB._sanitize_dsn(dsn)
    assert "<redacted>" in GaussDB._sanitize_dsn(url)


def test_get_cursor_commit_and_error_paths():
    db, mock_pool, mock_conn, mock_cursor = make_gaussdb()

    with db._get_cursor(commit=True) as cur:
        assert cur is mock_cursor

    mock_conn.set_client_encoding.assert_called_with("UTF8")
    mock_conn.commit.assert_called_once()
    mock_conn.rollback.assert_not_called()
    mock_pool.putconn.assert_called_with(mock_conn)

    db, mock_pool, mock_conn, mock_cursor = make_gaussdb()
    with pytest.raises(RuntimeError):
        with db._get_cursor(commit=False):
            raise RuntimeError("boom")

    assert mock_conn.rollback.call_count >= 1
    mock_pool.putconn.assert_called_with(mock_conn)


def test_get_cursor_skips_client_encoding_when_disabled():
    db, mock_pool, mock_conn, mock_cursor = make_gaussdb()
    db.client_encoding = None

    with db._get_cursor():
        pass

    mock_conn.set_client_encoding.assert_not_called()


def test_run_with_retry_retries_transient_error_then_succeeds(monkeypatch):
    db, *_ = make_gaussdb()
    attempts = {"count": 0}
    monkeypatch.setattr(gaussdb_module.time, "sleep", lambda *_: None)

    def op():
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise RuntimeError("connection reset by peer")
        return "ok"

    assert db._run_with_retry("search", op) == "ok"
    assert attempts["count"] == 2
    assert db.metrics["gaussdb_retry_count"] == 1


def test_run_with_retry_does_not_retry_non_retryable():
    db, *_ = make_gaussdb()
    with pytest.raises(RuntimeError):
        db._run_with_retry("search", lambda: (_ for _ in ()).throw(RuntimeError("bad sql")))


def test_record_latency_and_increment_metric_cover_no_observability_and_slow_warning(caplog):
    db, *_ = make_gaussdb()
    db.enable_observability = False
    db._increment_metric("x")
    db._record_latency("search", 0.0, "success")
    assert db.metrics == {}

    db.enable_observability = True
    db.slow_query_ms = -1
    with caplog.at_level(logging.WARNING):
        db._record_latency("search", 0.0, "success")
    assert "Slow GaussDB operation" in caplog.text
    assert db.metrics["gaussdb_search_latency_ms_count"] == 1


def test_vector_sql_helpers_and_distribution_clause():
    db, *_ = make_gaussdb(vector_metric="l2")
    db.id_column_type = "varchar"
    db.distribution_mode = "hash"

    assert db._vector_operator == "<->"
    assert db._vector_index_metric == "L2"
    assert db._id_column_sql() == "VARCHAR(36)"
    assert db._payload_column_sql() == "JSONB"
    assert "DISTRIBUTE BY HASH" in db._create_table_suffix_sql("id")
    with pytest.raises(ValueError):
        db.distribution_mode = "bad"
        db._distribution_clause_sql("id")


def test_payload_value_decode_payload_and_vector_literal():
    db, *_ = make_gaussdb()
    assert db._payload_value({"text": "你好"}) == '{"text": "你好"}'
    assert db._decode_payload(None) == {}
    assert db._decode_payload({"k": 1}) == {"k": 1}
    assert db._decode_payload('{"k": 2}') == {"k": 2}
    assert db._decode_payload(DummyMap()) == {"k": "v"}
    assert db._vector_literal([1, 2.5]) == "[1.0,2.5]"


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("128MB", 128 * 1024 * 1024),
        ("1 GiB", 1024 ** 3),
        (2048, 2048),
        ("bad", None),
        (None, None),
    ],
)
def test_parse_memory_setting_bytes(value, expected):
    assert GaussDB._parse_memory_setting_bytes(value) == expected


def test_ensure_schema_creates_when_missing():
    db, *_ = make_gaussdb()
    cur = MagicMock()
    cur.fetchone.return_value = (0,)

    db._ensure_schema(cur)

    sqls = executed_sql(cur)
    assert "information_schema.schemata" in sqls
    assert f'CREATE SCHEMA "{db.schema}"' in sqls


def test_ensure_schema_skips_when_present():
    db, *_ = make_gaussdb()
    cur = MagicMock()
    cur.fetchone.return_value = (1,)

    db._ensure_schema(cur)
    assert "CREATE SCHEMA" not in executed_sql(cur)


def test_create_col_builds_table_and_indexes():
    db, *_ = make_gaussdb()
    cur_cm = MagicMock()
    cur = MagicMock()
    cur_cm.__enter__.return_value = cur
    with patch.object(db, "_get_cursor", return_value=cur_cm), patch.object(
        db, "_run_with_retry", side_effect=lambda op, func: func()
    ), patch.object(db, "_ensure_schema") as ensure_schema, patch.object(
        db, "_create_schema_meta"
    ) as create_meta, patch.object(
        db, "_upsert_schema_meta"
    ) as upsert_meta, patch.object(
        db, "_ensure_indexes"
    ) as ensure_indexes:
        db.create_col()

    sqls = executed_sql(cur)
    assert "CREATE TABLE IF NOT EXISTS" in sqls
    ensure_schema.assert_called_once()
    create_meta.assert_called_once_with(cur)
    upsert_meta.assert_called_once()
    ensure_indexes.assert_called_once()


def test_create_schema_meta_upsert_and_vector_index_emit_expected_sql():
    db, *_ = make_gaussdb()
    cur = MagicMock()

    db._create_schema_meta(cur)
    db._upsert_schema_meta(cur, db.collection_name, 1)
    db._create_vector_index(cur, db.table_name)

    sqls = executed_sql(cur)
    assert "CREATE TABLE IF NOT EXISTS" in sqls
    assert "MERGE INTO" in sqls
    assert "CREATE INDEX IF NOT EXISTS" in sqls


def test_vector_index_with_clause_and_maintenance_mem_paths():
    db, *_ = make_gaussdb(embedding_model_dims=1536)
    assert "enable_vector_copy=false" in db._vector_index_with_clause()

    cur = MagicMock()
    cur.fetchone.return_value = ("3GB",)
    db._set_vector_index_maintenance_work_mem(cur)
    assert "SET LOCAL maintenance_work_mem" not in executed_sql(cur)

    cur = MagicMock()

    def execute(sql, *params):
        if sql == "SHOW maintenance_work_mem":
            raise RuntimeError("show failed")

    cur.execute.side_effect = execute
    db._set_vector_index_maintenance_work_mem(cur)
    assert cur.execute.call_args_list[-1].args[0] == "SET LOCAL maintenance_work_mem = %s"


def test_create_bm25_index_failure_disables_bm25_and_handles_cleanup_failure(caplog):
    db, *_ = make_gaussdb()
    cur = MagicMock()

    def execute(sql, *params):
        if "CREATE INDEX" in sql:
            raise RuntimeError("bm25 create failed")
        if "ROLLBACK TO SAVEPOINT" in sql:
            raise RuntimeError("rollback failed")

    cur.execute.side_effect = execute
    with caplog.at_level(logging.WARNING):
        db._create_bm25_index(cur, db.table_name)

    assert db.bm25_enabled is False
    assert db.metrics["gaussdb_fallback_count"] == 1
    assert "BM25 index creation failed" in caplog.text


def test_create_filter_indexes_failure_continues(caplog):
    db, *_ = make_gaussdb()
    cur = MagicMock()

    def execute(sql, *params):
        if "CREATE INDEX IF NOT EXISTS" in sql and "user_id" in sql:
            raise RuntimeError("idx failed")

    cur.execute.side_effect = execute
    with caplog.at_level(logging.WARNING):
        db._create_filter_indexes(cur, db.table_name)

    assert db.metrics["gaussdb_fallback_count"] == 1
    assert "Filter index creation failed for key user_id" in caplog.text


def test_ensure_indexes_skips_bm25_when_disabled():
    db, *_ = make_gaussdb()
    db.bm25_enabled = False
    cur = MagicMock()
    with patch.object(db, "_create_vector_index") as vector_idx, patch.object(
        db, "_create_bm25_index"
    ) as bm25_idx, patch.object(db, "_create_filter_indexes") as filter_idx:
        db._ensure_indexes(cur, db.table_name)

    vector_idx.assert_called_once()
    bm25_idx.assert_not_called()
    filter_idx.assert_called_once()


def test_insert_validates_lengths_and_handles_empty_rows():
    db, *_ = make_gaussdb()
    with pytest.raises(ValueError):
        db.insert([[1.0]], payloads=[], ids=["a"])
    assert db.insert([], payloads=[], ids=[]) is None


def test_incoming_values_sql_and_insert_row():
    db, *_ = make_gaussdb()
    sql = db._incoming_values_sql(["id", "vector", "payload", "memory", "schema_version", "user_id"])
    assert "%s::UUID" in sql
    assert "%s::FLOATVECTOR" in sql
    row = db._insert_row([1.0, 2.0], {"memory": "m", "user_id": "u1"}, "id1")
    assert row[0] == "id1"
    assert row[3] == "m"
    assert row[-3] == "u1"


def test_search_keyword_search_and_search_batch_paths():
    db, *_ = make_gaussdb()
    cur_cm = MagicMock()
    cur = MagicMock()
    cur.fetchall.return_value = [("id1", 0.1, '{"k":"v"}')]
    cur_cm.__enter__.return_value = cur
    with patch.object(db, "_get_cursor", return_value=cur_cm), patch.object(
        db, "_run_with_retry", side_effect=lambda op, func: func()
    ):
        rows = db.search("q", [0.1, 0.2, 0.3], filters={"user_id": "u1"})
        assert rows[0].payload == {"k": "v"}

    db.bm25_enabled = False
    assert db.keyword_search("q") is None
    db.bm25_enabled = True
    assert db.keyword_search("   ") == []

    with patch.object(db, "search", side_effect=[[1], [2]]) as search:
        assert db.search_batch(["a", "b"], [[1], [2]], top_k=2, filters={"user_id": "u1"}) == [[1], [2]]
        assert search.call_count == 2
    with pytest.raises(ValueError):
        db.search_batch(["a"], [[1], [2]])
    assert db.search_batch([], []) == []


def test_keyword_search_failure_returns_none_and_success_applies_settings():
    db, *_ = make_gaussdb()
    db.bm25_enabled = True
    cur_cm = MagicMock()
    cur = MagicMock()
    cur_cm.__enter__.return_value = cur
    cur.fetchall.return_value = [("id1", 0.9, '{"k":1}')]
    with patch.object(db, "_get_cursor", return_value=cur_cm), patch.object(
        db, "_run_with_retry", side_effect=lambda op, func: func()
    ):
        rows = db.keyword_search("probe", filters={"user_id": "u1"})
        assert rows[0].payload == {"k": 1}
        assert "SET LOCAL bm25_ranking_metric" in executed_sql(cur)

    with patch.object(db, "_get_cursor", side_effect=RuntimeError("bm25 failed")), patch.object(
        db, "_run_with_retry", side_effect=lambda op, func: func()
    ):
        assert db.keyword_search("probe", filters={"user_id": "u1"}) is None


def test_update_delete_get_list_reset_and_col_helpers():
    db, *_ = make_gaussdb()
    assert db.update("id1") is None

    cur_cm = MagicMock()
    cur = MagicMock()
    cur.fetchone.side_effect = [("id1", '{"a":1}'), None, (5,)]
    cur.fetchall.side_effect = [
        [("table_a",), ("table_a_schema_meta",), ("mem0_gdb_probe_x",), ("table_b",)],
        [("idx_a",), ("idx_b",)],
        [("id2", '{"b":2}')],
    ]
    cur_cm.__enter__.return_value = cur
    with patch.object(db, "_get_cursor", return_value=cur_cm), patch.object(
        db, "_run_with_retry", side_effect=lambda op, func: func()
    ), patch.object(db, "_read_schema_version", return_value=3), patch.object(
        db, "delete_col"
    ) as delete_col, patch.object(db, "create_col") as create_col:
        db.update("id1", payload={"memory": "m", "user_id": "u1"})
        assert db.get("id1").payload == {"a": 1}
        assert db.get("missing") is None
        assert db.list_cols() == ["table_a", "table_b"]
        db.delete_col()
        info = db.col_info()
        assert info["schema_version"] == 3
        listed = db.list(filters={"user_id": "u1"})
        assert listed[0][0].payload == {"b": 2}
        db.reset()
        assert delete_col.call_count == 2
        create_col.assert_called_once()


def test_read_schema_version_returns_default_when_meta_missing_or_row_missing():
    db, *_ = make_gaussdb()
    cur = MagicMock()
    cur.fetchone.side_effect = [(False,), (True,), None]
    assert db._read_schema_version(cur) == 1
    assert db._read_schema_version(cur) == 1


def test_build_where_clause_and_scope_helpers_cover_guard_paths():
    db, *_ = make_gaussdb(require_scoped_filters=True)
    with pytest.raises(ValueError):
        db._build_where_clause({"category": "x"}, require_scope=True)

    db.require_scoped_filters = False
    assert db._build_where_clause(None, require_scope=True) == ("", [])
    with patch.object(db, "_build_filter_expression", return_value=("", [])):
        assert db._build_where_clause({"user_id": "u1"}, require_scope=False) == ("", [])

    assert db._has_scope_filter({"$and": [{"category": "x"}, {"user_id": "u1"}]}) is True
    assert db._has_scope_filter({"$or": [{"user_id": "u1"}, {"category": "x"}]}) is False
    assert db._has_scope_filter({"$not": [{"user_id": "u1"}]}) is False

    assert GaussDB._is_positive_scope_filter_value("*") is False
    assert GaussDB._is_positive_scope_filter_value({"eq": "u1"}) is True
    assert GaussDB._is_positive_scope_filter_value({"in": ["", None]}) is False


def test_build_filter_expression_and_field_helpers_cover_error_and_edge_paths():
    db, *_ = make_gaussdb()
    with pytest.raises(ValueError):
        db._build_filter_expression("bad")
    with pytest.raises(ValueError):
        db._build_filter_expression({"$and": "bad"})
    with pytest.raises(ValueError):
        db._build_filter_expression({"$not": "bad"})

    expr, params = db._build_filter_expression(
        {"$or": [{"user_id": {"eq": "u1"}}, {"user_id": {"in": ["u2", "u3"]}}]}
    )
    assert " OR " in expr
    assert params == ["u1", "u2", "u3"]

    assert db._build_field_filter("category", "*") == ("", [])
    with pytest.raises(ValueError):
        db._build_field_filter("category", {"regex": "x"})

    assert db._field_in_expression("category", [], negate=False) == ("1 = 0", [])
    assert db._field_in_expression("category", [], negate=True) == ("1 = 1", [])

    expr, params = db._field_sql("category")
    assert expr == "payload->>'category'"
    assert params == []

    with pytest.raises(ValueError):
        db._build_presence_filter("category", {"exists": True, "missing": False})
    with pytest.raises(ValueError):
        db._build_presence_filter("category", {"exists": "yes"})
    with pytest.raises(ValueError):
        db._build_presence_filter("category", {"unknown": True})

    db.metadata_schema = {"created_at": "datetime"}
    with pytest.raises(ValueError):
        db._build_range_filter("created_at", {})


def test_close_context_manager_and_del_handle_pool_cleanup():
    db, *_ = make_gaussdb()
    pool = db.connection_pool
    db.close()
    pool.closeall.assert_called_once()
    assert db.connection_pool is None

    db, *_ = make_gaussdb()
    with db as entered:
        assert entered is db
    assert db.connection_pool is None

    db = object.__new__(GaussDB)
    db.connection_pool = MagicMock()
    db.__del__()
    db.connection_pool.closeall.assert_called_once()


def test_init_auto_create_calls_create_col_when_collection_missing():
    mock_conn = MagicMock()
    mock_conn.get_parameter_status.return_value = "UTF8"
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    mock_cursor.fetchone.return_value = ("UTF8",)
    mock_pool = MagicMock()
    mock_pool.getconn.return_value = mock_conn

    with patch.object(GaussDB, "_create_connection_pool", return_value=mock_pool), patch.object(
        GaussDB, "_probe_capabilities"
    ), patch.object(GaussDB, "list_cols", return_value=[]), patch.object(GaussDB, "create_col") as create_col:
        GaussDB(collection_name="test_collection", embedding_model_dims=3, auto_create=True)

    create_col.assert_called_once()


def test_init_rejects_maxconn_less_than_minconn():
    with pytest.raises(ValueError, match="maxconn must be >= minconn"):
        GaussDBConfig(
            host="localhost",
            port=5432,
            user="test",
            password="test",
            minconn=3,
            maxconn=2,
        )


def test_create_connection_pool_success_uses_sanitized_dsn(caplog):
    db, *_ = make_gaussdb(connection_string="postgresql://user:secret@localhost:19995/mem0db")
    fake_pool_class = MagicMock(return_value="POOL")
    with patch.object(gaussdb_module, "ThreadedConnectionPool", fake_pool_class):
        with caplog.at_level(logging.INFO):
            pool = db._create_connection_pool()

    assert pool == "POOL"
    assert "Creating GaussDB connection pool" in caplog.text


def test_build_dsn_does_not_duplicate_ssl_when_already_present():
    db, *_ = make_gaussdb(
        connection_string="postgresql://u:p@h:1/db sslmode=require sslrootcert=/tmp/x"
    )
    dsn = db._build_dsn()
    assert dsn.count("sslmode=") == 1
    assert dsn.count("sslrootcert=") == 1


def test_probe_capabilities_handles_enable_vectordb_read_failure():
    db, *_ = make_gaussdb()
    db.bm25_enabled = False
    with patch.object(db, "_run_with_retry", side_effect=lambda op, fn: fn()), patch.object(
        db, "_set_vector_index_maintenance_work_mem"
    ), patch.object(
        db, "_get_cursor"
    ) as get_cursor:
        startup_cm = MagicMock()
        startup_cur = MagicMock()
        main_cm = MagicMock()
        main_cur = MagicMock()
        cleanup_cm = MagicMock()
        cleanup_cur = MagicMock()
        startup_cm.__enter__.return_value = startup_cur
        main_cm.__enter__.return_value = main_cur
        cleanup_cm.__enter__.return_value = cleanup_cur
        get_cursor.side_effect = [startup_cm, main_cm, cleanup_cm]
        startup_cur.execute.side_effect = RuntimeError("show failed")
        main_cur.execute.side_effect = lambda *args, **kwargs: None

        db._probe_capabilities()

    assert db.capabilities.vector_enabled is True
    assert "DROP TABLE IF EXISTS" in executed_sql(cleanup_cur)


def test_probe_capabilities_raises_when_enable_vectordb_is_off():
    db, *_ = make_gaussdb()
    with patch.object(db, "_run_with_retry", side_effect=lambda op, fn: fn()), patch.object(
        db, "_get_cursor"
    ) as get_cursor:
        startup_cm = MagicMock()
        startup_cur = MagicMock()
        cleanup_cm = MagicMock()
        cleanup_cur = MagicMock()
        startup_cm.__enter__.return_value = startup_cur
        cleanup_cm.__enter__.return_value = cleanup_cur
        get_cursor.side_effect = [startup_cm, cleanup_cm]
        startup_cur.fetchone.return_value = ("off",)

        with pytest.raises(RuntimeError, match="enable_vectordb is not enabled"):
            db._probe_capabilities()


def test_probe_capabilities_raises_friendly_dimension_error():
    db, *_ = make_gaussdb(embedding_model_dims=1536)
    db.bm25_enabled = False
    with patch.object(db, "_run_with_retry", side_effect=lambda op, fn: fn()), patch.object(
        db, "_get_cursor"
    ) as get_cursor:
        startup_cm = MagicMock()
        startup_cur = MagicMock()
        main_cm = MagicMock()
        main_cur = MagicMock()
        cleanup_cm = MagicMock()
        cleanup_cur = MagicMock()
        startup_cm.__enter__.return_value = startup_cur
        main_cm.__enter__.return_value = main_cur
        cleanup_cm.__enter__.return_value = cleanup_cur
        get_cursor.side_effect = [startup_cm, main_cm, cleanup_cm]
        startup_cur.fetchone.return_value = ("on",)
        main_cur.execute.side_effect = RuntimeError("The vector exceeds the max dimension.")

        with pytest.raises(RuntimeError, match="vector dimension limit exceeded"):
            db._probe_capabilities()


def test_probe_capabilities_outer_bm25_exception_disables_bm25(caplog):
    db, *_ = make_gaussdb()
    db.bm25_enabled = True
    with patch.object(db, "_run_with_retry", side_effect=lambda op, fn: fn()), patch.object(
        db, "_set_vector_index_maintenance_work_mem"
    ), patch.object(
        db, "_get_cursor"
    ) as get_cursor, patch.object(db, "_create_bm25_index", side_effect=RuntimeError("bm25 exploded")):
        startup_cm = MagicMock()
        startup_cur = MagicMock()
        main_cm = MagicMock()
        main_cur = MagicMock()
        cleanup_cm = MagicMock()
        cleanup_cur = MagicMock()
        startup_cm.__enter__.return_value = startup_cur
        main_cm.__enter__.return_value = main_cur
        cleanup_cm.__enter__.return_value = cleanup_cur
        get_cursor.side_effect = [startup_cm, main_cm, cleanup_cm]
        startup_cur.fetchone.return_value = ("on",)
        main_cur.execute.side_effect = [None, None]

        with caplog.at_level(logging.WARNING):
            db._probe_capabilities()

    assert db.bm25_enabled is False
    assert "BM25 probe failed" in caplog.text


def test_probe_capabilities_logs_cleanup_failure(caplog):
    db, *_ = make_gaussdb()
    with patch.object(db, "_run_with_retry", side_effect=lambda op, fn: fn()), patch.object(
        db, "_set_vector_index_maintenance_work_mem"
    ), patch.object(
        db, "_get_cursor"
    ) as get_cursor, patch.object(db, "_create_bm25_index"):
        db.bm25_enabled = False
        startup_cm = MagicMock()
        startup_cur = MagicMock()
        main_cm = MagicMock()
        main_cur = MagicMock()
        cleanup_cm = MagicMock()
        startup_cm.__enter__.return_value = startup_cur
        main_cm.__enter__.return_value = main_cur
        cleanup_cm.__enter__.side_effect = RuntimeError("cleanup failed")
        get_cursor.side_effect = [startup_cm, main_cm, cleanup_cm]
        startup_cur.fetchone.return_value = ("on",)
        main_cur.execute.side_effect = lambda *args, **kwargs: None

        with caplog.at_level(logging.DEBUG):
            db._probe_capabilities()

    assert "Failed to clean up GaussDB probe table" in caplog.text


def test_create_col_updates_distance_choice():
    db, *_ = make_gaussdb()
    cur_cm = MagicMock()
    cur = MagicMock()
    cur_cm.__enter__.return_value = cur
    with patch.object(db, "_get_cursor", return_value=cur_cm), patch.object(
        db, "_run_with_retry", side_effect=lambda op, func: func()
    ), patch.object(db, "_ensure_schema"), patch.object(db, "_create_schema_meta"), patch.object(
        db, "_upsert_schema_meta"
    ), patch.object(db, "_ensure_indexes"):
        db.create_col(distance="l2")
    assert db.vector_metric == "l2"


def test_set_vector_index_maintenance_work_mem_handles_none_and_unparsed_target():
    db, *_ = make_gaussdb()
    cur = MagicMock()
    db.vector_index_maintenance_work_mem = None
    db._set_vector_index_maintenance_work_mem(cur)
    cur.execute.assert_not_called()

    db.vector_index_maintenance_work_mem = "weird"
    db._set_vector_index_maintenance_work_mem(cur)
    assert cur.execute.call_args.args[0] == "SET LOCAL maintenance_work_mem = %s"


def test_apply_bm25_settings_sets_expected_bm25_knobs():
    db, *_ = make_gaussdb()
    cur = MagicMock()
    db._apply_bm25_settings(cur)
    sql = executed_sql(cur)
    assert "SET LOCAL bm25_ranking_metric = 0" in sql
    assert "SET LOCAL bm25_ncandidates = 128" in sql
    assert "SET LOCAL enable_seqscan = off" in sql


def test_delete_col_executes_drop_statements():
    db, *_ = make_gaussdb()
    cur_cm = MagicMock()
    cur = MagicMock()
    cur_cm.__enter__.return_value = cur
    with patch.object(db, "_get_cursor", return_value=cur_cm), patch.object(
        db, "_run_with_retry", side_effect=lambda op, func: func()
    ):
        db.delete_col()

    sqls = executed_sql(cur)
    assert "DROP TABLE IF EXISTS" in sqls
    assert db.collection_name in sqls


def test_scope_helpers_cover_false_and_singleton_branches():
    assert GaussDB._is_positive_scope_filter_value([]) is False
    assert GaussDB._is_positive_scope_filter_value({"eq": ""}) is False
    assert GaussDB._is_positive_scope_filter_value({"in": "bad"}) is False

    db, *_ = make_gaussdb()
    assert db._has_scope_filter(None) is False
    assert db._has_scope_filter({"$or": []}) is False


def test_build_filter_expression_skips_empty_subexpressions_and_not_branch():
    db, *_ = make_gaussdb()
    expr, params = db._build_filter_expression({"$and": [{"category": "*"}], "$not": [{"category": "*"}]})
    assert expr == ""
    assert params == []


def test_build_field_filter_covers_scope_ne_nin_contains_and_list_singleton():
    db, *_ = make_gaussdb()
    expr, params = db._build_field_filter("user_id", {"ne": "u1"})
    assert expr == '"user_id" <> %s'
    assert params == ["u1"]

    expr, params = db._build_field_filter("category", {"nin": ["a", "b"]})
    assert " AND " in expr
    assert len(params) == 2

    expr, params = db._build_field_filter("title", {"contains": "100%_ok"})
    assert "LIKE %s ESCAPE '\\'" in expr
    assert params == ["%100\\%\\_ok%"]

    expr, params = db._build_field_filter("title", ["x"])
    assert expr == "payload @> %s::JSONB"
    assert params == ['{"title":"x"}']


def test_field_sql_and_in_expression_cover_json_expression_and_singletons():
    db, *_ = make_gaussdb()
    expr, params = db._field_sql("category")
    assert expr == "payload->>'category'"
    assert params == []

    expr, params = db._field_in_expression("category", ["x"], negate=True)
    assert expr == "(payload @> %s::JSONB) IS NOT TRUE"
    assert params == ['{"category":"x"}']

    expr, params = db._field_in_expression("user_id", ["u1", "u2"], negate=True)
    assert expr == '"user_id" NOT IN (%s, %s)'
    assert params == ["u1", "u2"]
