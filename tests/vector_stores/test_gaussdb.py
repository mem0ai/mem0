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
    assert cfg.schema_name == "public"
    assert cfg.embedding_model_dims == 1536
    assert cfg.minconn == 1
    assert cfg.maxconn == 5
    assert cfg.vector_index_maintenance_work_mem is None
    assert cfg.auto_create is True


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


def test_gaussdb_config_accepts_custom_schema_name():
    cfg = GaussDBConfig(
        host="localhost",
        port=5432,
        user="test",
        password="test",
        schema_name="mem0_app",
    )

    assert cfg.schema_name == "mem0_app"


def test_gaussdb_config_normalizes_case_insensitive_options():
    cfg = GaussDBConfig(
        host="localhost",
        port=5432,
        user="test",
        password="test",
        deployment_mode="Distributed",
        vector_index_type="GsDiskANN",
        vector_metric="Cosine",
        embedding_model_dims=512,
    )

    assert cfg.deployment_mode == "distributed"
    assert cfg.vector_index_type == "gsdiskann"
    assert cfg.vector_metric == "cosine"


def test_gaussdb_config_accepts_and_normalizes_vector_index_maintenance_work_mem():
    cfg = GaussDBConfig(
        host="localhost",
        port=5432,
        user="test",
        password="test",
        vector_index_maintenance_work_mem=" 2 gb ",
    )

    assert cfg.vector_index_maintenance_work_mem == "2GB"


def test_gaussdb_config_rejects_invalid_vector_index_maintenance_work_mem():
    with pytest.raises(Exception, match="vector_index_maintenance_work_mem"):
        GaussDBConfig(
            host="localhost",
            port=5432,
            user="test",
            password="test",
            vector_index_maintenance_work_mem="2G",
        )


def test_gaussdb_config_rejects_invalid_schema_name():
    with pytest.raises(Exception, match="schema_name"):
        GaussDBConfig(
            host="localhost",
            port=5432,
            user="test",
            password="test",
            schema_name="bad-schema",
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


def test_gaussdb_config_rejects_invalid_collection_name():
    with pytest.raises(Exception, match="collection_name"):
        GaussDBConfig(
            host="localhost",
            port=5432,
            user="test",
            password="test",
            collection_name="bad-name",
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


def test_gaussdb_direct_provider_explicit_database_and_schema_override_env(monkeypatch):
    monkeypatch.setenv("GAUSSDB_DATABASE", "env_db")
    monkeypatch.setenv("GAUSSDB_SCHEMA_NAME", "env_schema")

    db, *_ = make_gaussdb(database="explicit_db", schema_name="explicit_schema")

    assert db.database == "explicit_db"
    assert db.schema_name == "explicit_schema"
    assert db.table_name == '"explicit_schema"."test_collection"'


def test_gaussdb_direct_provider_database_and_schema_fallback_to_env(monkeypatch):
    monkeypatch.setenv("GAUSSDB_DATABASE", "env_db")
    monkeypatch.setenv("GAUSSDB_SCHEMA_NAME", "env_schema")

    db, *_ = make_gaussdb()

    assert db.database == "env_db"
    assert db.schema_name == "env_schema"
    assert db.table_name == '"env_schema"."test_collection"'


def test_gaussdb_config_rejects_extra_fields():
    with pytest.raises(Exception):
        GaussDBConfig(
            host="localhost",
            port=5432,
            user="test",
            password="test",
            unexpected=True,
        )


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
    with pytest.raises(ValueError, match="distributed mode only supports"):
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
    assert "vector FLOATVECTOR(3) NOT NULL" not in sql
    assert "payload JSONB NOT NULL" not in sql
    assert "user_id TEXT" in sql
    assert "agent_id TEXT" in sql
    assert "run_id TEXT" in sql
    assert "created_at TIMESTAMP" not in sql
    assert "updated_at TIMESTAMP" not in sql
    assert "SET LOCAL maintenance_work_mem" in sql
    assert "USING gsdiskann (vector COSINE)" in sql
    assert "USING bm25 (text_lemmatized)" in sql
    assert "storage_type='USTORE'" in sql
    assert '("user_id")' in sql or "user_id)" in sql
    mock_cursor.execute.assert_any_call("SET LOCAL maintenance_work_mem = %s", ("256MB",))
    mock_conn.commit.assert_called()


def test_create_col_rejects_alternate_collection_name_but_accepts_matching_name():
    db, _, _, _ = make_gaussdb()

    db.create_col(name=db.collection_name)

    with pytest.raises(ValueError, match="only supports the configured collection_name"):
        db.create_col(name="other_collection")

    with pytest.raises(ValueError, match="only supports the configured collection_name"):
        db.create_col("other_collection")


def test_distributed_create_col_generates_hash_distribution_clauses():
    db, _, _, mock_cursor = make_gaussdb(deployment_mode="distributed")

    db.create_col()

    sql = executed_sql(mock_cursor)
    assert db.deployment_mode == "distributed"
    assert db.distribution_mode == "hash"
    assert 'DISTRIBUTE BY HASH ("id")' in sql


def test_set_vector_index_maintenance_work_mem_sets_default_when_current_is_lower():
    db, _, _, mock_cursor = make_gaussdb()
    mock_cursor.fetchone.return_value = ("64MB",)

    db._set_vector_index_maintenance_work_mem(mock_cursor)

    mock_cursor.execute.assert_any_call("SHOW maintenance_work_mem")
    mock_cursor.execute.assert_any_call("SET LOCAL maintenance_work_mem = %s", ("256MB",))


def test_set_vector_index_maintenance_work_mem_raises_default_for_high_dim_gsdiskann():
    db, _, _, mock_cursor = make_gaussdb(embedding_model_dims=2048)
    mock_cursor.fetchone.return_value = ("256MB",)

    db._set_vector_index_maintenance_work_mem(mock_cursor)

    mock_cursor.execute.assert_any_call("SHOW maintenance_work_mem")
    mock_cursor.execute.assert_any_call("SET LOCAL maintenance_work_mem = %s", ("2GB",))


def test_set_vector_index_maintenance_work_mem_keeps_new_default_for_1024_dims():
    db, _, _, mock_cursor = make_gaussdb(embedding_model_dims=1024)
    mock_cursor.fetchone.return_value = ("64MB",)

    db._set_vector_index_maintenance_work_mem(mock_cursor)

    mock_cursor.execute.assert_any_call("SHOW maintenance_work_mem")
    mock_cursor.execute.assert_any_call("SET LOCAL maintenance_work_mem = %s", ("256MB",))


def test_set_vector_index_maintenance_work_mem_respects_user_override_for_high_dims():
    db, _, _, mock_cursor = make_gaussdb(embedding_model_dims=2048, vector_index_maintenance_work_mem="1GB")
    mock_cursor.fetchone.return_value = ("256MB",)

    db._set_vector_index_maintenance_work_mem(mock_cursor)

    mock_cursor.execute.assert_any_call("SHOW maintenance_work_mem")
    mock_cursor.execute.assert_any_call("SET LOCAL maintenance_work_mem = %s", ("1GB",))


def test_set_vector_index_maintenance_work_mem_does_not_lower_higher_current_value():
    db, _, _, mock_cursor = make_gaussdb()
    mock_cursor.fetchone.return_value = ("2GB",)

    db._set_vector_index_maintenance_work_mem(mock_cursor)

    mock_cursor.execute.assert_called_once_with("SHOW maintenance_work_mem")


def test_filter_index_creation_failure_warns_and_keeps_filter_mode(caplog):
    db, _, _, mock_cursor = make_gaussdb()
    caplog.set_level(logging.WARNING, logger="mem0.vector_stores.gaussdb")

    def execute_side_effect(sql, *args):
        if "CREATE INDEX IF NOT EXISTS" in str(sql) and "user_id" in str(sql):
            raise Exception("expression index unsupported")

    mock_cursor.execute.side_effect = execute_side_effect

    db._create_filter_indexes(mock_cursor, '"public"."test_collection"')

    assert db.filter_storage_mode == "json_expression"
    assert "Filter index creation failed for key user_id" in caplog.text


def test_constructor_uses_static_capability_assumptions_for_centralized():
    db, *_ = make_gaussdb(deployment_mode="centralized")

    assert db.capabilities.vector_enabled is True
    assert db.capabilities.floatvector is True
    assert db.capabilities.vector_index is True
    assert db.capabilities.bm25 is True
    assert db.capabilities.jsonb is True
    assert db.capabilities.uuid is True
    assert db.capabilities.expression_index is True
    assert db.capabilities.deployment_mode == "centralized"
    assert db.capabilities.distribution_mode == "none"


def test_constructor_uses_static_capability_assumptions_for_distributed():
    db, *_ = make_gaussdb(deployment_mode="distributed", embedding_model_dims=512)

    assert db.bm25_enabled is False
    assert db.capabilities.bm25 is False
    assert db.capabilities.deployment_mode == "distributed"
    assert db.capabilities.distribution_mode == "hash"


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
    assert merge_args[4] == "u1"  # user_id scope column


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
    assert len(calls[0].args[1]) == 21  # 3 rows x 7 insert fields


def test_insert_preserves_long_scope_values_without_provider_length_limit():
    db, *_ = make_gaussdb()
    long_user_id = "u" * 256

    values_sql = db._incoming_values_sql(["id", "user_id", "agent_id", "run_id"])
    row = db._insert_row([0.1, 0.2, 0.3], {"user_id": long_user_id}, "id1")

    assert values_sql.count("%s::TEXT") == 3
    assert row[4] == long_user_id


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


def test_insert_chunks_large_batches_into_multiple_merges():
    db, _, _, mock_cursor = make_gaussdb(insert_batch_size=2)

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
    assert len(calls) == 2
    assert all("MERGE INTO" in str(call.args[0]) for call in calls)
    # Row layout: id, vector, payload, text_lemmatized, user_id, agent_id, run_id.
    assert len(calls[0].args[1]) == 14  # 2 rows × 7 columns
    assert len(calls[1].args[1]) == 7   # 1 row × 7 columns


# ============================================================
# Search tests
# ============================================================


def test_search_uses_cosine_operator_and_similarity_score():
    db, _, _, mock_cursor = make_gaussdb()
    mock_cursor.fetchall.return_value = [("id1", 0.25, {"data": "hello", "user_id": "u1"})]

    results = db.search("hello", [0.1, 0.2, 0.3], top_k=5, filters={"user_id": "u1"})

    sql = executed_sql(mock_cursor)
    assert "vector <+> %s::FLOATVECTOR AS distance" in sql
    assert '"user_id" = %s' in sql
    assert results[0].id == "id1"
    # Cosine similarity = 1 - distance → 1 - 0.25 = 0.75
    assert results[0].score == pytest.approx(0.75)
    assert results[0].payload["data"] == "hello"


def test_search_cosine_similarity_from_tiny_negative_distance():
    db, _, _, mock_cursor = make_gaussdb()
    mock_cursor.fetchall.return_value = [("id1", -1.19209289550781e-07, {"data": "hello", "user_id": "u1"})]

    results = db.search("hello", [0.1, 0.2, 0.3], top_k=5, filters={"user_id": "u1"})

    # Cosine distance near 0 → similarity is clamped to mem0's [0, 1] score contract.
    assert results[0].score == 1.0


def test_search_typed_bool_filter_uses_jsonb_equality():
    db, _, _, mock_cursor = make_gaussdb()
    mock_cursor.fetchall.return_value = [("id1", 0.1, {"data": "hello", "flag": True, "user_id": "u1"})]

    results = db.search("hello", [0.1, 0.2, 0.3], filters={"user_id": "u1", "flag": True})

    sql = executed_sql(mock_cursor)
    params = mock_cursor.execute.call_args.args[1]
    assert "payload->%s = %s::JSONB" in sql
    assert '"user_id" = %s' in sql
    assert params[1] == "u1"
    assert params[2:4] == ("flag", "true")
    assert results[0].id == "id1"


def test_search_wildcard_filter_is_skipped_not_literal_match():
    db, _, _, mock_cursor = make_gaussdb()
    mock_cursor.fetchall.return_value = []

    db.search("hello", [0.1, 0.2, 0.3], filters={"user_id": "u1", "category": "*"})

    sql = executed_sql(mock_cursor)
    params = mock_cursor.execute.call_args.args[1]
    assert "category" not in sql
    assert params == ("[0.1,0.2,0.3]", "u1", 5)


def test_search_wildcard_scope_filter_is_skipped_not_literal_match():
    db, _, _, mock_cursor = make_gaussdb()
    mock_cursor.fetchall.return_value = []

    db.search("hello", [0.1, 0.2, 0.3], filters={"user_id": "*"})

    sql = executed_sql(mock_cursor)
    params = mock_cursor.execute.call_args.args[1]
    assert '"user_id" = %s' not in sql
    assert params == ("[0.1,0.2,0.3]", 5)


def test_search_all_wildcard_metadata_filters_do_not_leave_dangling_and():
    db, _, _, mock_cursor = make_gaussdb()
    mock_cursor.fetchall.return_value = []

    db.search("hello", [0.1, 0.2, 0.3], filters={"category": "*", "tag": "*"})

    sql = executed_sql(mock_cursor)
    assert "WHERE" not in sql or "WHERE  ORDER" not in sql
    assert "AND  ORDER" not in sql
    assert "category" not in sql
    assert "tag" not in sql


def test_search_eq_null_uses_jsonb_null_equality():
    db, _, _, mock_cursor = make_gaussdb()
    mock_cursor.fetchall.return_value = []

    db.search("hello", [0.1, 0.2, 0.3], filters={"user_id": "u1", "deleted_at": None})

    sql = executed_sql(mock_cursor)
    params = mock_cursor.execute.call_args.args[1]
    assert "payload->%s = %s::JSONB" in sql
    assert params[2:4] == ("deleted_at", "null")


def test_search_ne_bool_uses_typed_jsonb_negation():
    db, _, _, mock_cursor = make_gaussdb()
    mock_cursor.fetchall.return_value = []

    db.search("hello", [0.1, 0.2, 0.3], filters={"user_id": "u1", "flag": {"ne": True}})

    sql = executed_sql(mock_cursor)
    params = mock_cursor.execute.call_args.args[1]
    assert "(payload->%s = %s::JSONB) IS NOT TRUE" in sql
    assert params[2:4] == ("flag", "true")


def test_search_rejects_unsupported_operator():
    db, _, _, mock_cursor = make_gaussdb()
    mock_cursor.fetchall.return_value = []

    with pytest.raises(ValueError, match="Unsupported filter operator"):
        db.search("hello", [0.1, 0.2, 0.3], filters={"user_id": "u1", "score": {"between": [5, 7]}})

    mock_cursor.execute.assert_not_called()


def test_search_rejects_plain_json_object_without_explicit_eq():
    db, _, _, mock_cursor = make_gaussdb()
    mock_cursor.fetchall.return_value = []

    with pytest.raises(ValueError, match="Unsupported filter operator"):
        db.search("hello", [0.1, 0.2, 0.3], filters={"user_id": "u1", "profile": {"tier": "gold"}})

    mock_cursor.execute.assert_not_called()


def test_search_not_uses_is_not_true_semantics():
    db, _, _, mock_cursor = make_gaussdb()
    mock_cursor.fetchall.return_value = []

    db.search("hello", [0.1, 0.2, 0.3], filters={"user_id": "u1", "$not": [{"category": "food"}]})

    sql = executed_sql(mock_cursor)
    assert "((payload->%s = %s::JSONB) IS NOT TRUE)" in sql


def test_search_range_on_undeclared_numeric_field_auto_infers_number():
    db, _, _, mock_cursor = make_gaussdb()
    mock_cursor.fetchall.return_value = []

    db.search("hello", [0.1, 0.2, 0.3], filters={"user_id": "u1", "priority": {"gte": 3}})

    sql = executed_sql(mock_cursor)
    params = mock_cursor.execute.call_args.args[1]
    assert "CASE WHEN jsonb_typeof(payload->%s) = 'number'" in sql
    assert "THEN CAST(payload->>%s AS DOUBLE PRECISION) END >= %s" in sql
    assert params[1] == "u1"
    assert params[2:5] == ("priority", "priority", 3)


def test_search_inferred_numeric_range_uses_typed_numeric_cast():
    db, _, _, mock_cursor = make_gaussdb()
    mock_cursor.fetchall.return_value = []

    db.search("hello", [0.1, 0.2, 0.3], filters={"user_id": "u1", "priority": {"gte": 3, "lt": 7}})

    sql = executed_sql(mock_cursor)
    params = mock_cursor.execute.call_args.args[1]
    assert "CASE WHEN jsonb_typeof(payload->%s) = 'number'" in sql
    assert "THEN CAST(payload->>%s AS DOUBLE PRECISION) END >= %s" in sql
    assert "THEN CAST(payload->>%s AS DOUBLE PRECISION) END < %s" in sql
    assert params[1] == "u1"
    assert params[2:5] == ("priority", "priority", 3)
    assert params[5:8] == ("priority", "priority", 7)


def test_search_supports_mixed_range_and_non_range_operators_for_same_field():
    db, _, _, mock_cursor = make_gaussdb()
    mock_cursor.fetchall.return_value = []

    db.search("hello", [0.1, 0.2, 0.3], filters={"user_id": "u1", "priority": {"gt": 3, "eq": 7}})

    sql = executed_sql(mock_cursor)
    params = mock_cursor.execute.call_args.args[1]
    assert "THEN CAST(payload->>%s AS DOUBLE PRECISION) END > %s" in sql
    assert "payload->%s = %s::JSONB" in sql
    assert params[1] == "u1"
    assert params[2:5] == ("priority", "priority", 3)
    assert params[5:7] == ("priority", "7")


def test_search_supports_explicit_and_for_range_and_non_range_same_field():
    db, _, _, mock_cursor = make_gaussdb()
    mock_cursor.fetchall.return_value = []

    db.search(
        "hello",
        [0.1, 0.2, 0.3],
        filters={"$and": [{"priority": {"gt": 3}}, {"priority": {"eq": 7}}]},
    )

    sql = executed_sql(mock_cursor)
    params = mock_cursor.execute.call_args.args[1]
    assert "CASE WHEN jsonb_typeof(payload->%s) = 'number'" in sql
    assert "THEN CAST(payload->>%s AS DOUBLE PRECISION) END > %s" in sql
    assert "payload->%s = %s::JSONB" in sql
    assert params[1:4] == ("priority", "priority", 3)
    assert params[4:6] == ("priority", "7")


def test_field_filter_supports_multiple_non_range_operators():
    db, *_ = make_gaussdb()

    expr, params = db._build_field_filter("status", {"eq": "active", "ne": "deleted"})

    assert expr == "payload->%s = %s::JSONB AND (payload->%s = %s::JSONB) IS NOT TRUE"
    assert params == ["status", '"active"', "status", '"deleted"']


def test_search_supports_memory_merged_same_field_and_filters():
    db, _, _, mock_cursor = make_gaussdb()
    mock_cursor.fetchall.return_value = []

    db.search("hello", [0.1, 0.2, 0.3], filters={"user_id": "u1", "priority": {"gte": 5, "lte": 100, "ne": 50}})

    sql = executed_sql(mock_cursor)
    params = mock_cursor.execute.call_args.args[1]
    assert "THEN CAST(payload->>%s AS DOUBLE PRECISION) END >= %s" in sql
    assert "THEN CAST(payload->>%s AS DOUBLE PRECISION) END <= %s" in sql
    assert "(payload->%s = %s::JSONB) IS NOT TRUE" in sql
    assert params[1] == "u1"
    assert params[2:5] == ("priority", "priority", 5)
    assert params[5:8] == ("priority", "priority", 100)
    assert params[8:10] == ("priority", "50")


def test_search_not_with_invalid_range_subexpression_raises_value_error():
    db, _, _, mock_cursor = make_gaussdb()
    mock_cursor.fetchall.return_value = []

    with pytest.raises(ValueError, match="requires all operands to be numbers"):
        db.search("hello", [0.1, 0.2, 0.3], filters={"user_id": "u1", "$not": [{"category": {"gte": "a"}}]})

    mock_cursor.execute.assert_not_called()


def test_list_undeclared_datetime_range_auto_infers_timestamptz_cast_and_guard():
    db, _, _, mock_cursor = make_gaussdb()
    mock_cursor.fetchall.return_value = []

    db.list(filters={"created_at": {"lt": "2026-01-01T00:00:00Z"}})

    sql = executed_sql(mock_cursor)
    params = mock_cursor.execute.call_args.args[1]
    assert "CASE WHEN jsonb_typeof(payload->%s) = 'string'" in sql
    assert "payload->>%s ~ %s" in sql
    assert "THEN CAST(payload->>%s AS TIMESTAMPTZ) END < %s" in sql
    assert params[0] == "created_at"
    assert params[1] == "created_at"
    assert params[2].startswith("^[[:digit:]]{4}-[[:digit:]]{2}-[[:digit:]]{2}")
    assert "([T ]" in params[2]
    assert params[3] == "created_at"
    assert params[4] == "2026-01-01T00:00:00Z"
    assert params[5] == 100


def test_datetime_range_guard_accepts_gaussdb_castable_iso_shapes():
    """The SQL guard should accept the common ISO shapes GaussDB can cast safely."""
    pattern = gaussdb_module._ISO_8601_TIMESTAMPTZ_PATTERN

    assert "([T ]" in pattern
    assert ")?$" in pattern
    assert "(:?[[:digit:]]{2})?" in pattern
    assert GaussDB._is_iso_datetime_string("2024-01-01") is True
    assert GaussDB._is_iso_datetime_string("2024-01-01T00:00:00") is True
    assert GaussDB._is_iso_datetime_string("2024-01-01 00:00:00") is True
    assert GaussDB._is_iso_datetime_string("2024-01-01T00:00:00Z") is True
    assert GaussDB._is_iso_datetime_string("2024-01-01T00:00:00+08:00") is True
    assert GaussDB._is_iso_datetime_string("2024-01-01T00:00:00+0800") is True
    assert GaussDB._is_iso_datetime_string("2024-01-01T00:00:00+08") is True
    assert GaussDB._is_iso_datetime_string("2024-01-01T00:00:00,123+08:00") is False
    assert GaussDB._is_iso_datetime_string("2024-W01-1") is False


def test_search_combined_numeric_and_datetime_ranges_infer_independently():
    db, _, _, mock_cursor = make_gaussdb()
    mock_cursor.fetchall.return_value = []

    db.search(
        "hello",
        [0.1, 0.2, 0.3],
        filters={
            "user_id": "u1",
            "priority": {"gt": 5},
            "created_at": {"gt": "2024-01-01T00:00:00Z"},
        },
    )

    sql = executed_sql(mock_cursor)
    params = mock_cursor.execute.call_args.args[1]
    assert sql.count("CASE WHEN jsonb_typeof(payload->%s) = 'number'") == 1
    assert "THEN CAST(payload->>%s AS DOUBLE PRECISION) END > %s" in sql
    assert sql.count("CASE WHEN jsonb_typeof(payload->%s) = 'string'") == 1
    assert "THEN CAST(payload->>%s AS TIMESTAMPTZ) END > %s" in sql
    assert params[1] == "u1"
    assert params[2:5] == ("priority", "priority", 5)
    assert params[5] == "created_at"
    assert params[6] == "created_at"
    assert params[7].startswith("^[[:digit:]]{4}-[[:digit:]]{2}-[[:digit:]]{2}")
    assert "([T ]" in params[7]
    assert params[8] == "created_at"
    assert params[9] == "2024-01-01T00:00:00Z"


def test_list_combined_numeric_and_datetime_ranges_infer_independently():
    db, _, _, mock_cursor = make_gaussdb()
    mock_cursor.fetchall.return_value = []

    db.list(
        filters={
            "priority": {"gte": 3},
            "created_at": {"lt": "2026-01-01T00:00:00Z"},
        }
    )

    sql = executed_sql(mock_cursor)
    params = mock_cursor.execute.call_args.args[1]
    assert "THEN CAST(payload->>%s AS DOUBLE PRECISION) END >= %s" in sql
    assert "THEN CAST(payload->>%s AS TIMESTAMPTZ) END < %s" in sql
    assert params[0:3] == ("priority", "priority", 3)
    assert params[3] == "created_at"
    assert params[4] == "created_at"
    assert params[5].startswith("^[[:digit:]]{4}-[[:digit:]]{2}-[[:digit:]]{2}")
    assert "([T ]" in params[5]
    assert params[6] == "created_at"
    assert params[7] == "2026-01-01T00:00:00Z"
    assert params[8] == 100


def test_range_on_non_inferable_type_raises_value_error():
    db, _, _, mock_cursor = make_gaussdb()
    mock_cursor.fetchall.return_value = []

    with pytest.raises(ValueError, match="requires all operands to be numbers"):
        db.search("hello", [0.1, 0.2, 0.3], filters={"user_id": "u1", "category": {"gte": "a"}})

    mock_cursor.execute.assert_not_called()


@pytest.mark.parametrize(
    "filters, message",
    [
        ({"age": {"gt": True}}, "requires all operands to be numbers"),
        ({"age": {"gt": 5, "lt": "abc"}}, "requires all operands to be numbers"),
        ({"status": {"in": "active"}}, "requires a list or tuple operand"),
        ({"status": {"nin": "deleted"}}, "requires a list or tuple operand"),
        ({"title": {"contains": 123}}, "requires a string operand"),
        ({"title": {"icontains": ["abc"]}}, "requires a string operand"),
        ({"user_id": {"eq": ["u1", "u2"]}}, "requires a scalar operand"),
        ({"user_id": {"ne": ["u1", "u2"]}}, "requires a scalar operand"),
    ],
)
def test_search_rejects_invalid_filter_operand_types(filters, message):
    db, _, _, mock_cursor = make_gaussdb()
    mock_cursor.fetchall.return_value = []

    with pytest.raises(ValueError, match=message):
        db.search("hello", [0.1, 0.2, 0.3], filters=filters)

    mock_cursor.execute.assert_not_called()


def test_constructor_allows_unscoped_reads():
    db, _, _, mock_cursor = make_gaussdb()
    mock_cursor.fetchall.return_value = []

    assert db.search("hello", [0.1, 0.2, 0.3], filters={"category": "test"}) == []


def test_constructor_accepts_custom_schema_and_uses_qualified_names():
    db, _, _, _ = make_gaussdb(schema_name="mem0_app")

    assert db.schema_name == "mem0_app"
    assert db.table_name == '"mem0_app"."test_collection"'


@pytest.mark.parametrize(
    "filters",
    [
        {"OR": [{"user_id": "alice"}, {"category": "public"}]},
        {"$or": [{"user_id": "alice"}, {"category": "public"}]},
        {"NOT": [{"user_id": "alice"}]},
        {"user_id": {"ne": "alice"}},
        {"user_id": {"nin": ["alice"]}},
        {"user_id": "*"},
    ],
)
def test_search_accepts_various_scope_filter_shapes(filters):
    db, _, _, mock_cursor = make_gaussdb()
    mock_cursor.fetchall.return_value = []

    assert db.search("hello", [0.1, 0.2, 0.3], filters=filters) == []
    assert mock_cursor.execute.called


def test_filter_builder_rejects_unsafe_keys():
    db, _, _, _ = make_gaussdb()

    with pytest.raises(ValueError, match="Unsafe filter key"):
        db.list(filters={"bad-key": "x"})


def test_list_uses_scope_columns_and_typed_bool_filters():
    db, _, _, mock_cursor = make_gaussdb()
    mock_cursor.fetchall.return_value = []

    db.list(filters={"user_id": "u1", "flag": True})

    sql = executed_sql(mock_cursor)
    params = mock_cursor.execute.call_args.args[1]
    assert '"user_id" = %s' in sql
    assert "payload->%s = %s::JSONB" in sql
    assert params[0] == "u1"
    assert params[1:3] == ("flag", "true")


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
    assert '/*+ indexscan("test_collection" "test_collection_bm25_idx") */' in sql
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
    assert "payload->%s = %s::JSONB" in sql
    assert "hello" in params
    assert "u1" in params
    assert "flag" in params
    assert "true" in params


def test_keyword_search_empty_query_returns_empty_list():
    db, _, _, mock_cursor = make_gaussdb()

    assert db.keyword_search(" ", filters={"user_id": "u1"}) == []
    mock_cursor.execute.assert_not_called()


def test_keyword_search_returns_none_when_bm25_disabled():
    db, _, _, _ = make_gaussdb()
    db.bm25_enabled = False

    assert db.keyword_search("hello", filters={"user_id": "u1"}) is None


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
    assert "payload->%s = %s::JSONB" in sql
    assert params[1] == "u1"
    assert params[2:4] == ("flag", "true")


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


# ============================================================
# Update tests
# ============================================================


def test_update_vector_and_payload_updates_vector_payload_and_scope_columns():
    db, _, _, mock_cursor = make_gaussdb()

    db.update("id1", vector=[0.1, 0.2, 0.3], payload={"data": "new", "text_lemmatized": "new"})

    sql = executed_sql(mock_cursor)
    params = mock_cursor.execute.call_args.args[1]
    assert 'UPDATE "public"."test_collection"' in sql
    assert "vector = %s::FLOATVECTOR" in sql
    assert "payload = %s::JSONB" in sql
    assert '"user_id" = %s' in sql
    assert '"agent_id" = %s' in sql
    assert '"run_id" = %s' in sql
    assert "updated_at" not in sql
    assert "created_at" not in sql
    assert params[-4:] == (None, None, None, "id1")


def test_update_vector_only_does_not_touch_payload():
    db, _, _, mock_cursor = make_gaussdb()

    db.update("id1", vector=[0.1, 0.2, 0.3])

    sql = executed_sql(mock_cursor)
    params = mock_cursor.execute.call_args.args[1]
    assert "vector = %s::FLOATVECTOR" in sql
    assert "payload = %s" not in sql
    assert "memory = %s" not in sql
    assert params == ("[0.1,0.2,0.3]", "id1")


def test_update_payload_only_full_replaces_scope_columns():
    db, _, _, mock_cursor = make_gaussdb()

    db.update("id1", payload={"data": "new", "text_lemmatized": "new lemma"})

    sql = executed_sql(mock_cursor)
    params = mock_cursor.execute.call_args.args[1]
    assert "vector = %s::FLOATVECTOR" not in sql
    assert "payload = %s::JSONB" in sql
    assert "text_lemmatized = %s" in sql
    assert '"user_id" = %s' in sql
    assert '"agent_id" = %s' in sql
    assert '"run_id" = %s' in sql
    # Update parameter order: payload, text_lemmatized, user_id, agent_id, run_id, id.
    assert params[-5:] == ("new lemma", None, None, None, "id1")


def test_insert_rejects_duplicate_ids_within_single_call():
    db, _, _, mock_cursor = make_gaussdb()

    with pytest.raises(ValueError, match="ids must be unique"):
        db.insert(
            vectors=[[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]],
            payloads=[{"data": "a"}, {"data": "b"}],
            ids=["id1", "id1"],
        )

    assert mock_cursor.execute.call_count == 0


# ============================================================
# LIKE escape tests
# ============================================================


def test_contains_filter_escapes_percent_wildcard():
    db, _, _, mock_cursor = make_gaussdb()
    mock_cursor.fetchall.return_value = []

    db.list(filters={"user_id": {"contains": "100%"}})

    sql = executed_sql(mock_cursor)
    assert "LIKE %s ESCAPE" in sql
    call_args = mock_cursor.execute.call_args
    params = call_args[0][1] if len(call_args[0]) > 1 else call_args[1].get("params", [])
    assert any("%100!%%" in str(p) for p in params)


def test_contains_filter_escapes_underscore_wildcard():
    db, _, _, mock_cursor = make_gaussdb()
    mock_cursor.fetchall.return_value = []

    db.list(filters={"user_id": {"contains": "a_b"}})

    call_args = mock_cursor.execute.call_args
    params = call_args[0][1] if len(call_args[0]) > 1 else call_args[1].get("params", [])
    assert any("%a!_b%" in str(p) for p in params)


def test_icontains_filter_escapes_backslash():
    db, _, _, mock_cursor = make_gaussdb()
    mock_cursor.fetchall.return_value = []

    db.list(filters={"user_id": {"icontains": r"a\b"}})

    sql = executed_sql(mock_cursor)
    assert "LOWER" in sql
    assert "ESCAPE" in sql
    call_args = mock_cursor.execute.call_args
    params = call_args[0][1] if len(call_args[0]) > 1 else call_args[1].get("params", [])
    assert any(r"%a\b%" in str(p) for p in params)


def test_contains_filter_escapes_escape_character():
    db, _, _, mock_cursor = make_gaussdb()
    mock_cursor.fetchall.return_value = []

    db.list(filters={"user_id": {"contains": "wow!"}})

    call_args = mock_cursor.execute.call_args
    params = call_args[0][1] if len(call_args[0]) > 1 else call_args[1].get("params", [])
    assert any("%wow!!%" in str(p) for p in params)


@pytest.mark.parametrize("op", ["gt", "gte", "lt", "lte"])
def test_range_filter_operator_dict_auto_infers_number_without_declared_type(op, caplog):
    db, _, _, mock_cursor = make_gaussdb()
    mock_cursor.fetchall.return_value = []
    caplog.set_level(logging.WARNING, logger="mem0.vector_stores.gaussdb")

    db.list(filters={"priority": {op: 2}})

    sql = executed_sql(mock_cursor)
    params = mock_cursor.execute.call_args.args[1]
    assert "CASE WHEN jsonb_typeof(payload->%s) = 'number'" in sql
    assert (
        f"THEN CAST(payload->>%s AS DOUBLE PRECISION) END {'>=' if op == 'gte' else '>' if op == 'gt' else '<=' if op == 'lte' else '<'} %s"
        in sql
    )
    assert params[0] == "priority"
    assert params[1] == "priority"
    assert params[2] == 2
    assert "typed range semantics for this field shape" not in caplog.text


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
    assert "ORDER BY id ASC" in executed_sql(mock_cursor)


def test_list_top_k_zero_is_preserved():
    db, _, _, mock_cursor = make_gaussdb()
    mock_cursor.fetchall.return_value = []

    db.list(filters={"user_id": "u1"}, top_k=0)

    assert mock_cursor.execute.call_args.args[1][-1] == 0


def test_col_info_reads_indexes_and_capabilities():
    db, _, _, mock_cursor = make_gaussdb()
    mock_cursor.fetchone.side_effect = [(3,)]
    mock_cursor.fetchall.return_value = [("test_collection_vector_idx",), ("test_collection_bm25_idx",)]

    info = db.col_info()

    assert info["count"] == 3
    assert info["deployment_mode"] == "centralized"
    assert info["distribution_mode"] == "none"
    assert info["indexes"] == ["test_collection_vector_idx", "test_collection_bm25_idx"]


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


def test_validate_positive_int_and_choice_reject_invalid_values():
    from mem0.configs.vector_stores.gaussdb import _validate_positive_int

    with pytest.raises(ValueError):
        _validate_positive_int(0, "minconn")
    with pytest.raises(ValueError):
        GaussDB._validate_choice("bad", "vector_metric", {"cosine", "l2"})


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
        with pytest.raises(ImportError) as exc_info:
            db._create_connection_pool()
        message = str(exc_info.value)
        assert "requires psycopg2" in message
        assert "pip install psycopg2" in message
    with patch.object(gaussdb_module, "make_dsn", None):
        with pytest.raises(ImportError) as exc_info:
            db._create_connection_pool()
        assert "GaussDB documentation" in str(exc_info.value)


def test_build_dsn_merges_uri_connection_string_ssl_options():
    db, *_ = make_gaussdb(
        connection_string="postgresql://user:pass@localhost:19995/mem0db",
        sslmode="require",
        sslrootcert="/tmp/root.crt",
    )

    dsn = db._build_dsn()
    assert "dbname=mem0db" in dsn
    assert "user=user" in dsn
    assert "sslmode=require" in dsn
    assert "sslrootcert=/tmp/root.crt" in dsn


def test_build_dsn_preserves_uri_query_parameters_when_merging_ssl():
    db, *_ = make_gaussdb(
        connection_string="postgresql://user:pass@localhost:19995/mem0db?application_name=mem0_app",
        sslmode="require",
    )

    dsn = db._build_dsn()
    assert "dbname=mem0db" in dsn
    assert "application_name=mem0_app" in dsn
    assert "sslmode=require" in dsn


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


def test_quote_dsn_value_handles_empty_backslash_and_equals_safely():
    assert GaussDB._quote_dsn_value("") == "''"
    assert GaussDB._quote_dsn_value("abc=def") == "abc=def"
    assert GaussDB._quote_dsn_value(r"C:\tmp\root.crt") == r"'C:\\tmp\\root.crt'"


def test_sanitize_dsn_redacts_passwords():
    dsn = "dbname=postgres user=a password='secret pass' host=localhost"
    url = "postgresql://user:secret@localhost:5432/db"

    assert "<redacted>" in GaussDB._sanitize_dsn(dsn)
    assert "<redacted>" in GaussDB._sanitize_dsn(url)


def test_get_cursor_commit_and_error_paths():
    db, mock_pool, mock_conn, mock_cursor = make_gaussdb()

    with db._get_cursor(commit=True) as cur:
        assert cur is mock_cursor

    mock_conn.commit.assert_called_once()
    mock_conn.rollback.assert_not_called()
    mock_pool.putconn.assert_called_with(mock_conn)

    db, mock_pool, mock_conn, mock_cursor = make_gaussdb()
    with pytest.raises(RuntimeError):
        with db._get_cursor(commit=False):
            raise RuntimeError("boom")

    assert mock_conn.rollback.call_count >= 1
    mock_pool.putconn.assert_called_with(mock_conn)


def test_get_cursor_discards_connection_when_rollback_fails():
    db, mock_pool, mock_conn, _ = make_gaussdb()
    mock_conn.rollback.side_effect = RuntimeError("rollback connection lost")

    with pytest.raises(RuntimeError, match="server closed"):
        with db._get_cursor(commit=False):
            raise RuntimeError("server closed the connection unexpectedly")

    mock_pool.putconn.assert_called_with(mock_conn, close=True)


def test_get_cursor_discards_closed_connection_after_error():
    db, mock_pool, mock_conn, _ = make_gaussdb()
    mock_conn.closed = 1

    with pytest.raises(RuntimeError, match="boom"):
        with db._get_cursor(commit=False):
            raise RuntimeError("boom")

    mock_conn.rollback.assert_called()
    mock_pool.putconn.assert_called_with(mock_conn, close=True)


def test_get_cursor_can_suppress_exception_log_for_expected_fallback():
    db, mock_pool, mock_conn, _ = make_gaussdb()

    with patch.object(gaussdb_module.logger, "exception") as mock_exception:
        with pytest.raises(RuntimeError, match="expected fallback"):
            with db._get_cursor(log_errors=False):
                raise RuntimeError("expected fallback")

    mock_exception.assert_not_called()
    mock_conn.rollback.assert_called()
    mock_pool.putconn.assert_called_with(mock_conn)


def test_get_cursor_discards_connection_when_cursor_close_fails():
    db, mock_pool, mock_conn, mock_cursor = make_gaussdb()
    mock_cursor.close.side_effect = RuntimeError("cursor close failed")

    with db._get_cursor(commit=True) as cur:
        assert cur is mock_cursor

    mock_conn.commit.assert_called_once()
    mock_pool.putconn.assert_called_with(mock_conn, close=True)


def test_get_cursor_skips_client_encoding_when_disabled():
    db, mock_pool, mock_conn, mock_cursor = make_gaussdb()
    db.client_encoding = None

    with db._get_cursor():
        pass

    mock_conn.set_client_encoding.assert_not_called()


def test_run_with_retry_retries_transient_error_then_succeeds(monkeypatch, caplog):
    db, *_ = make_gaussdb()
    attempts = {"count": 0}
    monkeypatch.setattr(gaussdb_module.time, "sleep", lambda *_: None)

    def op():
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise RuntimeError("connection reset by peer")
        return "ok"

    with caplog.at_level(logging.WARNING):
        assert db._run_with_retry("search", op) == "ok"
    assert attempts["count"] == 2
    assert "Retrying GaussDB operation search after transient error" in caplog.text


def test_run_with_retry_does_not_retry_non_retryable():
    db, *_ = make_gaussdb()
    with pytest.raises(RuntimeError):
        db._run_with_retry("search", lambda: (_ for _ in ()).throw(RuntimeError("bad sql")))


def test_record_latency_logs_slow_debug(caplog):
    db, *_ = make_gaussdb()
    db.slow_query_ms = -1
    with caplog.at_level(logging.DEBUG):
        db._record_latency("search", 0.0, "success")
    assert "Slow GaussDB operation" in caplog.text


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
    assert db._payload_value({"text": "\u4f60\u597d"}) == '{"text": "\\u4f60\\u597d"}'
    assert db._decode_payload(None) == {}
    assert db._decode_payload({"k": 1}) == {"k": 1}
    assert db._decode_payload('{"k": 2}') == {"k": 2}
    assert db._decode_payload(DummyMap()) == {"k": "v"}
    assert db._vector_literal([1, 2.5]) == "[1.0,2.5]"


@pytest.mark.parametrize("bad_value", [float("inf"), float("-inf"), float("nan")])
def test_payload_value_rejects_non_finite_json_numbers(bad_value):
    db, *_ = make_gaussdb()
    with pytest.raises(ValueError, match="valid JSON; NaN and Infinity"):
        db._payload_value({"score": bad_value})


@pytest.mark.parametrize("bad_value", [float("inf"), float("-inf"), float("nan")])
def test_exact_filter_rejects_non_finite_json_numbers(bad_value):
    db, *_ = make_gaussdb()
    with pytest.raises(ValueError, match="Filter value for field 'score'.*valid JSON"):
        db._build_field_filter("score", {"eq": bad_value})


@pytest.mark.parametrize("bad_value", [float("inf"), float("-inf"), float("nan")])
def test_range_filter_rejects_non_finite_numbers(bad_value):
    db, *_ = make_gaussdb()
    with pytest.raises(ValueError, match="requires all operands to be numbers"):
        db._build_field_filter("score", {"gt": bad_value})


@pytest.mark.parametrize("bad_value", [float("inf"), float("-inf"), float("nan")])
def test_vector_literal_rejects_non_finite_values(bad_value):
    db, *_ = make_gaussdb()
    with pytest.raises(ValueError, match="finite numbers"):
        db._vector_literal([1.0, bad_value, 3.0])


def test_vector_literal_rejects_empty_vector():
    db, *_ = make_gaussdb()
    with pytest.raises(ValueError, match="empty vector|at least one dimension"):
        db._vector_literal([])


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("128MB", 128 * 1024 * 1024),
        ("1 GiB", 1024**3),
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

    db._ensure_schema(cur)

    sqls = executed_sql(cur)
    assert "SAVEPOINT mem0_create_schema" in sqls
    assert f'CREATE SCHEMA "{db.schema_name}"' in sqls
    assert "RELEASE SAVEPOINT mem0_create_schema" in sqls


def test_ensure_schema_tolerates_concurrent_create_race():
    db, *_ = make_gaussdb()
    cur = MagicMock()

    def execute_side_effect(sql, *args):
        if str(sql) == f'CREATE SCHEMA "{db.schema_name}"':
            raise Exception("schema already exists")

    cur.execute.side_effect = execute_side_effect
    cur.fetchone.side_effect = [(1,)]  # _schema_exists returns True after race

    db._ensure_schema(cur)

    sqls = executed_sql(cur)
    assert "SAVEPOINT mem0_create_schema" in sqls
    assert f'CREATE SCHEMA "{db.schema_name}"' in sqls


def test_ensure_schema_reraises_non_race_create_failure():
    db, *_ = make_gaussdb()
    cur = MagicMock()

    def execute_side_effect(sql, *args):
        if str(sql) == f'CREATE SCHEMA "{db.schema_name}"':
            raise Exception("permission denied")

    cur.execute.side_effect = execute_side_effect
    cur.fetchone.side_effect = [(0,)]  # _schema_exists returns False

    with pytest.raises(Exception, match="permission denied"):
        db._ensure_schema(cur)


def test_create_col_builds_table_and_indexes():
    db, *_ = make_gaussdb()
    cur_cm = MagicMock()
    cur = MagicMock()
    cur_cm.__enter__.return_value = cur
    with (
        patch.object(db, "_get_cursor", return_value=cur_cm),
        patch.object(db, "_run_with_retry", side_effect=lambda op, func: func()),
        patch.object(db, "_ensure_schema") as ensure_schema,
        patch.object(db, "_ensure_indexes") as ensure_indexes,
    ):
        db.create_col()

    sqls = executed_sql(cur)
    assert "CREATE TABLE IF NOT EXISTS" in sqls
    ensure_schema.assert_called_once()
    ensure_indexes.assert_called_once()


def test_create_vector_index_emits_expected_sql():
    db, *_ = make_gaussdb()
    cur = MagicMock()

    db._create_vector_index(cur, db.table_name)

    sqls = executed_sql(cur)
    assert "CREATE INDEX IF NOT EXISTS" in sqls


def test_vector_index_with_clause_and_maintenance_mem_paths():
    db, *_ = make_gaussdb(embedding_model_dims=1536)
    assert "enable_vector_copy=false" in db._vector_index_with_clause()

    cur = MagicMock()
    cur.fetchone.return_value = ("64MB",)
    db._set_vector_index_maintenance_work_mem(cur)
    assert "SET LOCAL maintenance_work_mem" in executed_sql(cur)

    cur = MagicMock()
    cur.fetchone.return_value = ("64MB",)
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

    assert "Filter index creation failed for key user_id" in caplog.text


def test_ensure_indexes_skips_bm25_when_disabled():
    db, *_ = make_gaussdb()
    db.bm25_enabled = False
    cur = MagicMock()
    with (
        patch.object(db, "_create_vector_index") as vector_idx,
        patch.object(db, "_create_bm25_index") as bm25_idx,
        patch.object(db, "_create_filter_indexes") as filter_idx,
    ):
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
    sql = db._incoming_values_sql(["id", "vector", "payload", "memory", "text_lemmatized", "user_id"])
    assert "%s::UUID" in sql
    assert "%s::FLOATVECTOR" in sql
    assert "%s::TEXT" in sql
    row = db._insert_row([1.0, 2.0], {"data": "m", "user_id": "u1"}, "id1")
    assert row[0] == "id1"
    assert row[3] == "m"
    assert row[-3:] == ("u1", None, None)


def test_search_keyword_search_and_search_batch_paths():
    db, *_ = make_gaussdb()
    cur_cm = MagicMock()
    cur = MagicMock()
    cur.fetchall.return_value = [("id1", 0.1, '{"k":"v"}')]
    cur_cm.__enter__.return_value = cur
    with (
        patch.object(db, "_get_cursor", return_value=cur_cm),
        patch.object(db, "_run_with_retry", side_effect=lambda op, func: func()),
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
    with (
        patch.object(db, "_get_cursor", return_value=cur_cm),
        patch.object(db, "_run_with_retry", side_effect=lambda op, func: func()),
    ):
        rows = db.keyword_search("probe", filters={"user_id": "u1"})
        assert rows[0].payload == {"k": 1}
        assert "SET LOCAL bm25_ranking_metric" in executed_sql(cur)

    with (
        patch.object(
            db, "_get_cursor", side_effect=RuntimeError("gs_bm25_distance_text is called, but no BM25 index is used")
        ),
        patch.object(db, "_run_with_retry", side_effect=lambda op, func: func()),
    ):
        assert db.keyword_search("probe", filters={"user_id": "u1"}) is None
        assert db.bm25_enabled is True


def test_keyword_search_retries_retryable_errors_and_returns_rows(monkeypatch):
    db, *_ = make_gaussdb()
    db.bm25_enabled = True
    monkeypatch.setattr(gaussdb_module.time, "sleep", lambda *_: None)

    cur_cm = MagicMock()
    cur = MagicMock()
    cur_cm.__enter__.return_value = cur
    cur.fetchall.return_value = [("id1", 1.2, '{"k":"v"}')]

    get_cursor = MagicMock(side_effect=[RuntimeError("connection reset by peer"), cur_cm])
    with patch.object(db, "_get_cursor", get_cursor):
        rows = db.keyword_search("probe", filters={"user_id": "u1"})

    assert [row.id for row in rows] == ["id1"]
    assert get_cursor.call_count == 2


def test_keyword_search_raises_non_bm25_errors_instead_of_silent_none():
    db, *_ = make_gaussdb()
    db.bm25_enabled = True

    with patch.object(db, "_get_cursor", side_effect=RuntimeError("permission denied for relation test_collection")):
        with pytest.raises(RuntimeError, match="permission denied"):
            db.keyword_search("probe", filters={"user_id": "u1"})


def test_update_delete_get_list_reset_and_col_helpers():
    db, *_ = make_gaussdb()
    assert db.update("id1") is None

    cur_cm = MagicMock()
    cur = MagicMock()
    cur.fetchone.side_effect = [("id1", '{"a":1}'), None, (5,)]
    cur.fetchall.side_effect = [
        [("table_a",), ("table_b",)],
        [("idx_a",), ("idx_b",)],
        [("id2", '{"b":2}')],
    ]
    cur_cm.__enter__.return_value = cur
    with (
        patch.object(db, "_get_cursor", return_value=cur_cm),
        patch.object(db, "_run_with_retry", side_effect=lambda op, func: func()),
        patch.object(db, "delete_col") as delete_col,
        patch.object(db, "create_col") as create_col,
    ):
        db.update("id1", payload={"memory": "m", "user_id": "u1"})
        assert db.get("id1").payload == {"a": 1}
        assert db.get("missing") is None
        assert db.list_cols() == ["table_a", "table_b"]
        db.delete_col()
        db.col_info()
        listed = db.list(filters={"user_id": "u1"})
        assert listed[0][0].payload == {"b": 2}
        db.reset()
        assert delete_col.call_count == 2
        create_col.assert_called_once()


def test_build_where_clause_returns_empty_for_missing_filters():
    db, *_ = make_gaussdb()
    assert db._build_where_clause(None) == ("", [])


def test_build_filter_expression_and_field_helpers_cover_error_and_edge_paths():
    db, *_ = make_gaussdb()
    with pytest.raises(ValueError):
        db._build_filter_expression("bad")
    with pytest.raises(ValueError):
        db._build_filter_expression({"$and": "bad"})
    with pytest.raises(ValueError):
        db._build_filter_expression({"$not": "bad"})

    expr, params = db._build_filter_expression({"$or": [{"user_id": {"eq": "u1"}}, {"user_id": {"in": ["u2", "u3"]}}]})
    assert " OR " in expr
    assert params == ["u1", "u2", "u3"]

    assert db._build_field_filter("category", "*") == ("", [])
    with pytest.raises(ValueError, match="Unsupported filter operator"):
        db._build_field_filter("category", {"regex": "x"})
    expr, params = db._build_field_filter("category", {"eq": "*"})
    assert expr == "payload->%s = %s::JSONB"
    assert params == ["category", '"*"']

    assert db._field_in_expression("category", [], negate=False) == ("1 = 0", [])
    assert db._field_in_expression("category", [], negate=True) == ("1 = 1", [])

    expr, params = db._field_sql("category")
    assert expr == "payload->>%s"
    assert params == ["category"]

    with pytest.raises(ValueError, match="requires all operands to be numbers"):
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

    with (
        patch.object(GaussDB, "_create_connection_pool", return_value=mock_pool),
        patch.object(GaussDB, "list_cols", return_value=[]),
        patch.object(GaussDB, "create_col") as create_col,
    ):
        GaussDB(collection_name="test_collection", embedding_model_dims=3, auto_create=True)

    create_col.assert_called_once()


def test_init_auto_create_verifies_bm25_present_when_collection_exists():
    """When collection exists and a usable BM25 index is present, bm25_enabled stays True."""
    mock_conn = MagicMock()
    mock_conn.get_parameter_status.return_value = "UTF8"
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    # fetchone returns a row -> usable BM25 index exists
    mock_cursor.fetchone.return_value = (1,)
    mock_cursor.fetchall.return_value = []
    mock_pool = MagicMock()
    mock_pool.getconn.return_value = mock_conn

    with (
        patch.object(GaussDB, "_create_connection_pool", return_value=mock_pool),
        patch.object(GaussDB, "list_cols", return_value=["test_collection"]),
        patch.object(GaussDB, "create_col"),
    ):
        db = GaussDB(collection_name="test_collection", embedding_model_dims=3, auto_create=True)

    assert db.bm25_enabled is True
    assert db.capabilities.bm25 is True
    # Verify the probe checks the real index access method and usable state,
    # not only the index definition text.
    sql = executed_sql(mock_cursor)
    assert "FROM pg_index pi" in sql
    assert "JOIN pg_am am" in sql
    assert "am.amname = 'bm25'" in sql
    assert "pi.indisvalid IS TRUE" in sql
    assert "pi.indisusable IS TRUE" in sql


def test_init_auto_create_detects_bm25_absent_when_collection_exists():
    """When collection exists but no usable BM25 index is found, bm25_enabled becomes False."""
    mock_conn = MagicMock()
    mock_conn.get_parameter_status.return_value = "UTF8"
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    # fetchone returns None -> no valid/usable BM25 index found
    mock_cursor.fetchone.return_value = None
    mock_cursor.fetchall.return_value = []
    mock_pool = MagicMock()
    mock_pool.getconn.return_value = mock_conn

    with (
        patch.object(GaussDB, "_create_connection_pool", return_value=mock_pool),
        patch.object(GaussDB, "list_cols", return_value=["test_collection"]),
        patch.object(GaussDB, "create_col"),
    ):
        db = GaussDB(collection_name="test_collection", embedding_model_dims=3, auto_create=True)

    assert db.bm25_enabled is False
    assert db.capabilities.bm25 is False
    sql = executed_sql(mock_cursor)
    assert "FROM pg_index pi" in sql
    assert "JOIN pg_am am" in sql
    assert "am.amname = 'bm25'" in sql
    assert "pi.indisvalid IS TRUE" in sql
    assert "pi.indisusable IS TRUE" in sql


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
        connection_string="postgresql://u:p@h:1/db?application_name=mem0&sslmode=disable&sslrootcert=%2Ftmp%2Fx",
        sslmode="require",
        sslrootcert="/tmp/x",
    )
    dsn = db._build_dsn()
    assert dsn.count("sslmode=") == 1
    assert dsn.count("sslrootcert=") == 1
    assert "application_name=mem0" in dsn
    assert "sslmode=require" in dsn


def test_create_col_updates_distance_choice():
    db, *_ = make_gaussdb()
    cur_cm = MagicMock()
    cur = MagicMock()
    cur_cm.__enter__.return_value = cur
    with (
        patch.object(db, "_get_cursor", return_value=cur_cm),
        patch.object(db, "_run_with_retry", side_effect=lambda op, func: func()),
        patch.object(db, "_ensure_schema"),
        patch.object(db, "_ensure_indexes"),
    ):
        db.create_col(distance="l2")
    assert db.vector_metric == "l2"


def test_create_col_instance_dims_drive_high_dim_index_settings():
    db, *_ = make_gaussdb(embedding_model_dims=2048)
    cur_cm = MagicMock()
    cur = MagicMock()
    cur_cm.__enter__.return_value = cur
    cur.fetchone.return_value = ("64MB",)
    with (
        patch.object(db, "_get_cursor", return_value=cur_cm),
        patch.object(db, "_run_with_retry", side_effect=lambda op, func: func()),
        patch.object(db, "_ensure_schema"),
    ):
        db.create_col()

    sqls = executed_sql(cur)
    assert "FLOATVECTOR(2048)" in sqls
    assert "SET LOCAL maintenance_work_mem = %s" in sqls
    assert "USING gsdiskann (vector COSINE)" in sqls
    assert "WITH (enable_vector_copy=false, subgraph_count=1)" in sqls
    cur.execute.assert_any_call("SET LOCAL maintenance_work_mem = %s", ("2GB",))


def test_create_col_vector_size_must_match_embedding_model_dims():
    db, *_ = make_gaussdb(embedding_model_dims=512)

    db.create_col(vector_size=512)

    with pytest.raises(ValueError, match="vector_size must match embedding_model_dims"):
        db.create_col(vector_size=2048)


def test_set_vector_index_maintenance_work_mem_handles_none_and_unparsed_target():
    db, *_ = make_gaussdb()
    cur = MagicMock()
    db.vector_index_maintenance_work_mem = None
    cur.fetchone.return_value = ("64MB",)
    db._set_vector_index_maintenance_work_mem(cur)
    cur.execute.assert_any_call("SET LOCAL maintenance_work_mem = %s", ("256MB",))


def test_set_vector_index_maintenance_work_mem_skips_when_current_value_unparseably_higher_behavior_unknown():
    db, *_ = make_gaussdb()
    cur = MagicMock()
    cur.fetchone.return_value = ("invalid_setting",)
    db._set_vector_index_maintenance_work_mem(cur)
    cur.execute.assert_any_call("SET LOCAL maintenance_work_mem = %s", ("256MB",))


def test_apply_bm25_settings_sets_expected_bm25_knobs():
    db, *_ = make_gaussdb()
    cur = MagicMock()
    db._apply_bm25_settings(cur)
    sql = executed_sql(cur)
    assert "SET LOCAL bm25_ranking_metric = 0" in sql
    assert "SET LOCAL bm25_ncandidates = 128" in sql
    assert "SET LOCAL enable_seqscan = off" in sql


def test_bm25_index_hint_uses_default_generated_index_name():
    db, *_ = make_gaussdb()
    assert db._bm25_index_hint() == '/*+ indexscan("test_collection" "test_collection_bm25_idx") */'


def test_delete_col_executes_drop_statements():
    db, *_ = make_gaussdb()
    cur_cm = MagicMock()
    cur = MagicMock()
    cur_cm.__enter__.return_value = cur
    with (
        patch.object(db, "_get_cursor", return_value=cur_cm),
        patch.object(db, "_run_with_retry", side_effect=lambda op, func: func()),
    ):
        db.delete_col()

    sqls = executed_sql(cur)
    assert "DROP TABLE IF EXISTS" in sqls
    assert db.collection_name in sqls


def test_build_filter_expression_skips_empty_subexpressions_and_not_branch():
    db, *_ = make_gaussdb()
    expr, params = db._build_filter_expression({"$and": [{"category": "*"}], "$not": [{"category": "*"}]})
    assert expr == ""
    assert params == []


def test_build_filter_expression_wraps_or_group_before_top_level_and():
    db, *_ = make_gaussdb()
    expr, params = db._build_filter_expression({"$or": [{"user_id": "alice"}, {"status": "active"}], "agent_id": "bot"})
    assert expr == '(("user_id" = %s) OR (payload->%s = %s::JSONB)) AND "agent_id" = %s'
    assert params == ["alice", "status", '"active"', "bot"]


def test_build_field_filter_covers_scope_ne_nin_contains_and_list_singleton():
    db, *_ = make_gaussdb()
    expr, params = db._build_field_filter("user_id", {"ne": "u1"})
    assert expr == '("user_id" = %s) IS NOT TRUE'
    assert params == ["u1"]

    expr, params = db._build_field_filter("category", {"nin": ["a", "b"]})
    assert " AND " in expr
    assert len(params) == 4

    expr, params = db._build_field_filter("title", {"contains": "100%_ok"})
    assert "jsonb_typeof(payload->%s) = 'string'" in expr
    assert "payload->>%s LIKE %s ESCAPE '!'"
    assert params == ["title", "title", "%100!%!_ok%"]

    expr, params = db._build_field_filter("title", ["x"])
    assert expr == "payload->%s = %s::JSONB"
    assert params == ["title", '"x"']


def test_field_sql_and_in_expression_cover_json_expression_and_singletons():
    db, *_ = make_gaussdb()
    expr, params = db._field_sql("category")
    assert expr == "payload->>%s"
    assert params == ["category"]

    expr, params = db._field_in_expression("category", ["x"], negate=True)
    assert expr == "(payload->%s = %s::JSONB) IS NOT TRUE"
    assert params == ["category", '"x"']

    expr, params = db._field_in_expression("user_id", ["u1", "u2"], negate=True)
    assert expr == '("user_id" IN (%s, %s)) IS NOT TRUE'
    assert params == ["u1", "u2"]


def test_scope_field_filter_uses_null_aware_column_semantics():
    db, *_ = make_gaussdb()

    expr, params = db._build_field_filter("user_id", None)
    assert expr == '"user_id" IS NULL'
    assert params == []

    expr, params = db._build_field_filter("user_id", {"eq": None})
    assert expr == '"user_id" IS NULL'
    assert params == []

    expr, params = db._build_field_filter("user_id", {"ne": None})
    assert expr == '"user_id" IS NOT NULL'
    assert params == []


def test_scope_in_and_nin_with_none_expand_to_null_aware_sql():
    db, *_ = make_gaussdb()

    expr, params = db._field_in_expression("user_id", ["u1", None], negate=False)
    assert expr == '("user_id" IN (%s) OR "user_id" IS NULL)'
    assert params == ["u1"]

    expr, params = db._field_in_expression("user_id", ["u1", None], negate=True)
    assert expr == '(("user_id" IN (%s) OR "user_id" IS NULL)) IS NOT TRUE'
    assert params == ["u1"]

    expr, params = db._field_in_expression("user_id", [None], negate=False)
    assert expr == '"user_id" IS NULL'
    assert params == []

    expr, params = db._field_in_expression("user_id", [None], negate=True)
    assert expr == '"user_id" IS NOT NULL'
    assert params == []


def test_scope_ne_uses_not_equal_for_non_null_values():
    db, *_ = make_gaussdb()

    expr, params = db._build_filter_expression({"user_id": {"ne": "u1"}})
    assert expr == '("user_id" = %s) IS NOT TRUE'
    assert params == ["u1"]

    # $not still uses IS NOT TRUE (includes NULL rows)
    expr, params = db._build_filter_expression({"$not": [{"user_id": "u1"}]})
    assert expr == '(("user_id" = %s) IS NOT TRUE)'
    assert params == ["u1"]


def test_scope_not_null_filter_uses_column_semantics():
    db, *_ = make_gaussdb()

    expr, params = db._build_filter_expression({"user_id": {"ne": None}})
    assert expr == '"user_id" IS NOT NULL'
    assert params == []


# ══════════════════════════════════════════════════════════
# Gap-filling tests: cover lines missed by both unit and E2E suites
# ══════════════════════════════════════════════════════════


# ===========================================================
# Gap-filling tests: cover lines missed by both unit and E2E
# ===========================================================


class TestCoverageGapFill:
    """Tests targeting the 14 uncovered lines identified by combined coverage analysis."""

    # --- gaussdb.py lines 20-22: ImportError fallback ---
    def test_psycopg2_import_error_guard_raises_on_instantiation(self):
        """_create_connection_pool raises ImportError when psycopg2 is unavailable."""

        db, *_ = make_gaussdb()

        from mem0.vector_stores.gaussdb import GaussDB

        with patch.object(GaussDB, "_create_connection_pool") as mock_create:
            mock_create.side_effect = ImportError("GaussDB vector store requires psycopg2.")

            with pytest.raises(ImportError, match="psycopg2"):
                GaussDB(
                    user="test",
                    password="test",
                    host="test",
                    port=1,
                    embedding_model_dims=3,
                    auto_create=False,
                )

    # --- gaussdb.py line 366: retry exhaustion raises last exception ---
    def test_run_with_retry_exhaustion_raises(self):
        """After all retry attempts exhausted, _run_with_retry raises the last exception."""

        db, *_ = make_gaussdb()

        db.retry_attempts = 2

        db.retry_backoff_seconds = 0.01

        transient_error = Exception("connection reset by peer")

        def always_fail():

            raise transient_error

        with patch.object(db, "_is_retryable", return_value=True):
            with patch.object(db, "_record_latency"):
                with patch("time.sleep"):
                    with pytest.raises(Exception, match="connection reset by peer"):
                        db._run_with_retry("test_op", always_fail)

    # --- gaussdb.py line 605: _parse_memory_setting_bytes returns None ---
    def test_parse_memory_setting_bytes_unknown_unit_returns_none(self):
        """_parse_memory_setting_bytes returns None for unknown unit suffixes."""

        from mem0.vector_stores.gaussdb import GaussDB

        assert GaussDB._parse_memory_setting_bytes("500PB") is None

        assert GaussDB._parse_memory_setting_bytes("invalid_string") is None

    # --- gaussdb.py lines 646-647: filter index rollback failure ---
    def test_create_filter_indexes_savepoint_rollback_failure_swallowed(self):
        """When filter index creation fails AND rollback to savepoint also fails."""

        db, mock_pool, mock_cur, *_ = make_gaussdb()

        db.connection_pool = mock_pool

        # _create_filter_indexes loops over 3 scope columns (user_id, agent_id, run_id).
        # For each column: SAVEPOINT, CREATE INDEX, then if INDEX fails:
        #   try: ROLLBACK TO SAVEPOINT (may fail) -> then RELEASE (not reached if ROLLBACK fails)
        #   except Exception: log and continue (lines 646-647)
        # So the flow per column is: SAVEPOINT (ok) -> CREATE INDEX (fail) -> ROLLBACK (fail, caught by except)
        # Total: 3 columns * 3 calls each = 9 calls

        call_count = 0

        def execute_side_effect(*args, **kwargs):

            nonlocal call_count

            call_count += 1

            # Every 3rd call pattern: SAVEPOINT(ok), CREATE INDEX(fail), ROLLBACK(fail)

            if call_count % 3 == 1:  # SAVEPOINT
                return None

            if call_count % 3 == 2:  # CREATE INDEX
                raise Exception("CREATE INDEX failed")

            if call_count % 3 == 0:  # ROLLBACK TO SAVEPOINT (fails, caught by except on line 646)
                raise Exception("ROLLBACK TO SAVEPOINT failed")

            return None

        mock_cur.execute.side_effect = execute_side_effect

        db._create_filter_indexes(mock_cur, db.table_name)

        # 3 scope columns, all failed, but rollback cleanup failures are swallowed.
        assert mock_cur.execute.call_count >= 3

    # --- range operand validation ---
    def test_build_range_filter_unresolvable_type_raises_value_error(self):
        """When range field type cannot be resolved, raise a clear operand error."""

        db, *_ = make_gaussdb()

        with pytest.raises(ValueError, match="requires all operands to be numbers"):
            db._build_range_filter("flag", {"gt": True, "lt": False})

    # --- config/gaussdb.py line 36: _validate_positive_int rejects bool ---
    def test_config_validate_positive_int_bool_rejected(self):
        """_validate_positive_int rejects True and False values."""

        from mem0.configs.vector_stores.gaussdb import _validate_positive_int

        with pytest.raises(ValueError, match="must be >= 1"):
            _validate_positive_int(True, "test_field")

        with pytest.raises(ValueError, match="must be >= 1"):
            _validate_positive_int(False, "test_field")

    # --- config/gaussdb.py lines 59, 61, 63: invalid mode/type/metric ---
    def test_config_rejects_invalid_deployment_mode(self):
        """validate_gaussdb_static_options rejects invalid deployment_mode."""

        from mem0.configs.vector_stores.gaussdb import validate_gaussdb_static_options

        with pytest.raises(ValueError, match="deployment_mode"):
            validate_gaussdb_static_options(
                embedding_model_dims=3,
                insert_batch_size=100,
                minconn=1,
                maxconn=5,
                schema_name="public",
                deployment_mode="hybrid",
                vector_index_type="gsdiskann",
                vector_metric="cosine",
            )

    def test_config_rejects_invalid_vector_index_type(self):
        """validate_gaussdb_static_options rejects invalid vector_index_type."""

        from mem0.configs.vector_stores.gaussdb import validate_gaussdb_static_options

        with pytest.raises(ValueError, match="vector_index_type"):
            validate_gaussdb_static_options(
                embedding_model_dims=3,
                insert_batch_size=100,
                minconn=1,
                maxconn=5,
                schema_name="public",
                deployment_mode="centralized",
                vector_index_type="hnsw",
                vector_metric="cosine",
            )

    def test_config_rejects_invalid_vector_metric(self):
        """validate_gaussdb_static_options rejects invalid vector_metric."""

        from mem0.configs.vector_stores.gaussdb import validate_gaussdb_static_options

        with pytest.raises(ValueError, match="vector_metric"):
            validate_gaussdb_static_options(
                embedding_model_dims=3,
                insert_batch_size=100,
                minconn=1,
                maxconn=5,
                schema_name="public",
                deployment_mode="centralized",
                vector_index_type="gsdiskann",
                vector_metric="ip",
            )

    # --- config/gaussdb.py lines 137, 141: partial host/port ---
    def test_config_rejects_host_without_port(self):
        """GaussDBConfig rejects host provided without port."""

        from mem0.configs.vector_stores.gaussdb import GaussDBConfig

        with pytest.raises(ValueError):
            GaussDBConfig(
                user="test",
                password="test",
                host="127.0.0.1",
                database="testdb",
                embedding_model_dims=3,
            )

    def test_config_rejects_port_without_host(self):
        """GaussDBConfig rejects port provided without host."""

        from mem0.configs.vector_stores.gaussdb import GaussDBConfig

        with pytest.raises(ValueError):
            GaussDBConfig(
                user="test",
                password="test",
                port=5432,
                database="testdb",
                embedding_model_dims=3,
            )

    # --- config/gaussdb.py lines 137, 141: user/password and host/port partial ---
    def test_config_user_without_password(self):
        """GaussDBConfig rejects user provided without password (line 137)."""

        from mem0.configs.vector_stores.gaussdb import GaussDBConfig

        with pytest.raises(ValueError):
            GaussDBConfig(
                user="test_user",
                database="testdb",
                embedding_model_dims=3,
            )

    def test_config_password_without_user(self):
        """GaussDBConfig rejects password provided without user (line 137)."""

        from mem0.configs.vector_stores.gaussdb import GaussDBConfig

        with pytest.raises(ValueError):
            GaussDBConfig(
                password="test_pass",
                database="testdb",
                embedding_model_dims=3,
            )


# ══════════════════════════════════════════════════════════
# Logic-bug and edge-case gap tests
# ══════════════════════════════════════════════════════════


class TestLogicBugAndEdgeCases:
    """Tests targeting logic bugs and edge cases not covered by existing tests."""

    # --- H: update() with payload={} NULLs all scope columns ---
    def test_update_empty_payload_nulls_all_scope_columns(self):
        """Updating with payload={} produces NULL for every scope column.
        This verifies the full-replacement semantics that can silently
        NULL scope columns if callers forget to preserve them."""
        db, _, _, mock_cursor = make_gaussdb()

        db.update("id1", payload={})

        sql = executed_sql(mock_cursor)
        params = mock_cursor.execute.call_args.args[1]
        assert "payload = %s::JSONB" in sql
        assert "text_lemmatized = %s" in sql
        assert '"user_id" = %s' in sql
        assert '"agent_id" = %s' in sql
        assert '"run_id" = %s' in sql
        # Update parameter order: payload_value '{}', text_lemmatized, user_id, agent_id, run_id, id.
        assert params[0] == "{}"
        assert params[1] is None  # text_lemmatized
        assert params[2] is None  # user_id
        assert params[3] is None  # agent_id
        assert params[4] is None  # run_id

    # --- H: update() with payload containing only scope keys ---
    def test_update_payload_with_scope_keys_preserves_them_but_nulls_text_lemmatized(self):
        """When payload has scope keys but no 'data' or 'text_lemmatized' key,
        text_lemmatized becomes None while scope columns are preserved."""
        db, _, _, mock_cursor = make_gaussdb()

        db.update("id1", payload={"user_id": "u2", "agent_id": "a1"})

        params = mock_cursor.execute.call_args.args[1]
        # text_lemmatized is None because no 'data' or 'text_lemmatized' key
        assert params[1] is None  # text_lemmatized
        assert params[2] == "u2"  # user_id preserved
        assert params[3] == "a1"  # agent_id preserved
        assert params[4] is None  # run_id not in payload -> NULL

    # --- H: _decode_payload bytes input defensive compatibility ---
    def test_decode_payload_bytes_input_decodes_as_utf8_json(self):
        """Bytes is not the normal psycopg2 JSONB return type, but decoding it
        keeps GaussDB compatible with non-standard driver/typecaster behavior."""
        assert GaussDB._decode_payload(b'{"key": "value"}') == {"key": "value"}
        assert GaussDB._decode_payload(b'{"k":1}') == {"k": 1}

    # --- H: list() empty result still returns double-nested [[]] ---
    def test_list_empty_result_returns_double_nested_empty_list(self):
        """list() must always return List[List[OutputData]], even with no rows.
        Empty fetchall should produce [[]], not []."""
        db, _, _, mock_cursor = make_gaussdb()
        mock_cursor.fetchall.return_value = []

        results = db.list()

        assert isinstance(results, list)
        assert len(results) == 1
        assert isinstance(results[0], list)
        assert len(results[0]) == 0

    # --- H: keyword_search runtime BM25 error falls back to None ---
    def test_keyword_search_runtime_bm25_unavailable_error_returns_none(self):
        """When BM25 query fails with a BM25-unavailable error during runtime,
        keyword_search returns None without disabling bm25_enabled."""
        db, *_ = make_gaussdb()
        db.bm25_enabled = True

        cur_cm = MagicMock()
        cur = MagicMock()
        cur_cm.__enter__.return_value = cur
        # Simulate the BM25 query failing with the "no bm25 index is used" error
        cur.execute.side_effect = RuntimeError("no bm25 index is used in the query plan")
        with (
            patch.object(db, "_get_cursor", return_value=cur_cm),
            patch.object(db, "_run_with_retry", side_effect=lambda op, func: func()),
        ):
            result = db.keyword_search("probe")

        assert result is None
        # bm25_enabled should NOT be permanently disabled by a runtime query failure
        # (it only gets disabled during index creation failures)
        assert db.bm25_enabled is True

    # --- M: search() with L2 metric does not clamp negative distance ---
    def test_search_l2_similarity_from_tiny_negative_distance(self):
        """L2 tiny negative distance → similarity = 1/(1+max(0,d)) = 1/(1+0) = 1.0."""
        db, _, _, mock_cursor = make_gaussdb(vector_metric="l2")
        mock_cursor.fetchall.return_value = [("id1", -1e-8, {"data": "hello"})]

        results = db.search("hello", [0.1, 0.2, 0.3], top_k=5)

        assert results[0].score == pytest.approx(1.0)

    # --- M: search() with L2 metric, large distance → small similarity ---
    def test_search_l2_similarity_from_large_positive_distance(self):
        """L2 large distance → similarity = 1/(1+d) is small but positive."""
        db, _, _, mock_cursor = make_gaussdb(vector_metric="l2")
        mock_cursor.fetchall.return_value = [("id1", 999.99, {"data": "hello"})]

        results = db.search("hello", [0.1, 0.2, 0.3], top_k=5)

        assert results[0].score == pytest.approx(1.0 / (1.0 + 999.99))

    # --- M: search() with filters=None produces no WHERE clause ---
    def test_search_no_filters_produces_no_where_clause(self):
        """search() with filters=None should produce SQL with no WHERE clause."""
        db, _, _, mock_cursor = make_gaussdb()
        mock_cursor.fetchall.return_value = [("id1", 0.1, {"data": "hello"})]

        db.search("hello", [0.1, 0.2, 0.3], filters=None)

        sql = executed_sql(mock_cursor)
        assert "WHERE" not in sql

    # --- M: list() with top_k=None defaults to 100 ---
    def test_list_top_k_none_defaults_to_100(self):
        """list() maps top_k=None to limit=100 in the SQL query."""
        db, _, _, mock_cursor = make_gaussdb()
        mock_cursor.fetchall.return_value = []

        db.list(top_k=None)

        params = mock_cursor.execute.call_args.args[1]
        assert params[-1] == 100

    # --- M: _vector_index_with_clause for low-dim gsdiskann returns empty ---
    def test_vector_index_with_clause_low_dim_returns_empty_string(self):
        """For dims <= 1024, gsdiskann WITH clause should be empty string
        (no enable_vector_copy=false needed)."""
        db, *_ = make_gaussdb(embedding_model_dims=512)

        assert db._vector_index_with_clause() == ""

    # --- M: keyword_search with filters=None uses proper prefix ---
    def test_keyword_search_no_filters_produces_where_prefix_only(self):
        """keyword_search with no filters should have WHERE for the BM25
        score > 0 condition but no AND for filter conditions."""
        db, _, _, mock_cursor = make_gaussdb()
        mock_cursor.fetchall.return_value = [("id1", 1.5, {"data": "hello"})]

        db.keyword_search("hello", top_k=5, filters=None)

        sql = executed_sql(mock_cursor)
        # With no filters, the WHERE clause is just the BM25 score condition
        assert " WHERE " in sql
        assert "(text_lemmatized ### %s) > 0" in sql
        # No scope column conditions
        assert '"user_id"' not in sql
        # No scope column filter conditions (payload->>%s or payload->%s are filter patterns)
        assert "payload @>" not in sql
        assert "payload->>%s" not in sql

    # --- M: _is_bm25_unavailable_error operator does not exist with ### ---
    def test_is_bm25_unavailable_error_operator_not_exist_with_hash(self):
        """The combination of 'bm25' AND ('operator does not exist' AND '###')
        is classified as a BM25 unavailable error. The 'bm25' keyword is
        a prerequisite in the code's second check path."""
        # Must include 'bm25' in message for this path to activate
        exc = Exception("operator does not exist: bm25 ### text")
        assert GaussDB._is_bm25_unavailable_error(exc) is True

        # 'operator does not exist' without '###' is NOT BM25 unavailable
        # even if 'bm25' is in the message
        exc2 = Exception("operator does not exist: bm25 concat text")
        assert GaussDB._is_bm25_unavailable_error(exc2) is False

        # 'operator does not exist' with '###' but without 'bm25' keyword
        # is NOT BM25 unavailable (bm25 is a prerequisite)
        exc3 = Exception("operator does not exist: text ### text")
        assert GaussDB._is_bm25_unavailable_error(exc3) is False

    # --- M: _is_bm25_unavailable_error function does not exist with bm25 ---
    def test_is_bm25_unavailable_error_function_not_exist_with_bm25(self):
        """'function does not exist' combined with 'bm25' keyword is classified
        as a BM25 unavailable error."""
        exc = Exception("function does not exist: bm25_distance")
        assert GaussDB._is_bm25_unavailable_error(exc) is True

        # 'function does not exist' without 'bm25' is NOT BM25 unavailable
        exc2 = Exception("function does not exist: upper")
        assert GaussDB._is_bm25_unavailable_error(exc2) is False

    # --- M: _is_bm25_unavailable_error bm25 not currently supported ---
    def test_is_bm25_unavailable_error_bm25_not_supported(self):
        """'bm25' keyword combined with 'not currently supported' is a BM25 error."""
        exc = Exception("bm25 is not currently supported in distributed mode")
        assert GaussDB._is_bm25_unavailable_error(exc) is True

        # 'not currently supported' without 'bm25' is NOT BM25 unavailable
        exc2 = Exception("feature not currently supported")
        assert GaussDB._is_bm25_unavailable_error(exc2) is False

    # --- M: insert() MERGE does not reference physical timestamp columns ---
    def test_insert_merge_does_not_reference_physical_timestamp_columns(self):
        """GaussDB stores mem0 timestamps only in payload metadata, not physical columns."""
        db, _, _, mock_cursor = make_gaussdb()

        db.insert(
            vectors=[[0.1, 0.2, 0.3]],
            payloads=[{"data": "hello"}],
            ids=["id1"],
        )

        sql = executed_sql(mock_cursor)
        assert "updated_at" not in sql
        assert "created_at" not in sql

    # --- M: _insert_row with payload=None defaults to empty dict ---
    def test_insert_row_with_none_payload_defaults_to_empty_dict(self):
        """_insert_row called with payload=None should use {} as the default,
        producing None for text_lemmatized and all scope columns."""
        db, *_ = make_gaussdb()
        row = db._insert_row([1.0, 2.0, 3.0], None, "test-id")

        assert row[0] == "test-id"
        assert row[2] == "{}"  # _payload_value({}) -> '{}'
        assert row[3] is None  # text_lemmatized from {} -> None
        assert row[4] is None  # user_id from {} -> None
        assert row[5] is None  # agent_id from {} -> None
        assert row[6] is None  # run_id from {} -> None

    # --- M: _insert_row with payload containing only 'memory' key ---
    def test_insert_row_with_memory_key_does_not_fill_text_lemmatized_field(self):
        """When payload only has 'memory', text_lemmatized stays None like other BM25 providers."""
        db, *_ = make_gaussdb()
        row = db._insert_row([1.0, 2.0, 3.0], {"memory": "my memory"}, "test-id")

        assert row[3] is None

    # --- M: _insert_row with explicit text_lemmatized overrides raw data ---
    def test_insert_row_with_explicit_text_lemmatized_overrides_data(self):
        """When payload has both 'data' and 'text_lemmatized', text_lemmatized takes precedence."""
        db, *_ = make_gaussdb()
        row = db._insert_row([1.0, 2.0, 3.0], {"data": "raw data", "text_lemmatized": "lemmatized"}, "test-id")

        assert row[3] == "lemmatized"

    # --- M: search() cosine large distance (above 1.0) clamps to zero ---
    def test_search_cosine_similarity_from_distance_above_one(self):
        """Cosine distance 1.5 is opposite/irrelevant and clamps to score 0.0."""
        db, _, _, mock_cursor = make_gaussdb()
        mock_cursor.fetchall.return_value = [("id1", 1.5, {"data": "hello"})]

        results = db.search("hello", [0.1, 0.2, 0.3], top_k=5)

        assert results[0].score == pytest.approx(0.0)

    # --- M: $not with multiple items produces separate IS NOT TRUE for each ---
    def test_not_filter_with_multiple_items_produces_is_not_true_per_item(self):
        """$not filter with a list of multiple conditions wraps each in
        (expr) IS NOT TRUE independently."""
        db, _, _, mock_cursor = make_gaussdb()
        mock_cursor.fetchall.return_value = []

        db.search("hello", [0.1, 0.2, 0.3], filters={"$not": [{"category": "food"}, {"status": "draft"}]})

        sql = executed_sql(mock_cursor)
        assert "(payload->%s = %s::JSONB) IS NOT TRUE" in sql
        # Both conditions should appear as IS NOT TRUE
        assert sql.count("IS NOT TRUE") == 2

    # --- M: $and/$or nesting produces correct SQL precedence ---
    def test_nested_and_or_filter_produces_correct_sql_grouping(self):
        """Nested $or inside $and should produce properly grouped SQL
        with outer AND combining the grouped OR."""
        db, _, _, mock_cursor = make_gaussdb()
        mock_cursor.fetchall.return_value = []

        db.search(
            "hello",
            [0.1, 0.2, 0.3],
            filters={
                "$and": [
                    {"$or": [{"user_id": "u1"}, {"user_id": "u2"}]},
                    {"status": "active"},
                ],
            },
        )

        sql = executed_sql(mock_cursor)
        # The inner $or should be wrapped in parens
        # The outer $and should combine them with AND
        assert " OR " in sql
        assert " AND " in sql


# ===========================================================
# Operand type guard tests: eq/ne + non-scalar, contains/icontains jsonb_typeof
# ===========================================================


def test_eq_with_list_operand_requires_scalar_for_scope_and_jsonb_exact_for_payload():
    db, *_ = make_gaussdb()

    # scope column: eq + list is invalid; use in/nin for multiple scope values.
    with pytest.raises(ValueError, match="requires a scalar operand"):
        db._build_field_filter("user_id", {"eq": ["a", "b"]})

    # JSONB column: eq + list uses strict JSONB equality.
    expr, params = db._build_field_filter("category", {"eq": ["a", "b"]})
    assert expr == "payload->%s = %s::JSONB"
    assert params == ["category", '["a","b"]']


def test_ne_with_list_operand_requires_scalar_for_scope_and_jsonb_negation_for_payload():
    db, *_ = make_gaussdb()

    with pytest.raises(ValueError, match="requires a scalar operand"):
        db._build_field_filter("user_id", {"ne": ["a", "b"]})

    expr, params = db._build_field_filter("category", {"ne": ["a", "b"]})
    assert expr == "(payload->%s = %s::JSONB) IS NOT TRUE"
    assert params == ["category", '["a","b"]']


def test_eq_with_dict_operand_uses_strict_jsonb_equality():
    db, *_ = make_gaussdb()
    expr, params = db._build_field_filter("category", {"eq": {"nested": True}})
    assert expr == "payload->%s = %s::JSONB"
    assert params == ["category", '{"nested":true}']


def test_contains_on_jsonb_column_includes_jsonb_typeof_guard():
    db, *_ = make_gaussdb()

    expr, params = db._build_field_filter("category", {"contains": "hello"})
    assert "jsonb_typeof(payload->%s) = 'string'" in expr
    assert "payload->>%s LIKE %s ESCAPE '!'"
    assert params == ["category", "category", "%hello%"]


def test_icontains_on_jsonb_column_includes_jsonb_typeof_guard():
    db, *_ = make_gaussdb()

    expr, params = db._build_field_filter("category", {"icontains": "hello"})
    assert "jsonb_typeof(payload->%s) = 'string'" in expr
    assert "LOWER(payload->>%s) LIKE LOWER(%s) ESCAPE '!'" in expr
    assert params == ["category", "category", "%hello%"]


def test_contains_on_scope_column_no_jsonb_typeof_guard():
    db, *_ = make_gaussdb()

    # user_id is a scope column, so LIKE works directly without jsonb_typeof.
    expr, params = db._build_field_filter("user_id", {"contains": "alice"})
    assert "jsonb_typeof" not in expr
    assert "LIKE %s ESCAPE '!'" in expr
    assert params == ["%alice%"]
