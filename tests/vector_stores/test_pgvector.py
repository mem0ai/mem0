import unittest
from unittest.mock import patch, MagicMock
from mem0.vector_stores.pgvector import PGVector, OutputData
import psycopg2
import uuid


class TestPGVector(unittest.TestCase):

    def setUp(self):
        self.db = PGVector(
            dbname="test_db",
            collection_name="test_collection",
            embedding_model_dims=128,
            user="test_user",
            password="test_password",
            host="localhost",
            port=5432,
            diskann=False,
        )
        self.db.conn = MagicMock()
        self.db.cur = MagicMock()

    def test_create_col(self):
        self.db.create_col(128)
        self.db.cur.execute.assert_called_with(
            """
            CREATE TABLE IF NOT EXISTS test_collection (
                id UUID PRIMARY KEY,
                vector vector(128),
                payload JSONB
            );
            """
        )
        self.db.conn.commit.assert_called_once()

    def test_insert(self):
        vectors = [[0.1, 0.2], [0.3, 0.4]]
        payloads = [{"key": "value1"}, {"key": "value2"}]
        ids = [str(uuid.uuid4()), str(uuid.uuid4())]

        with patch("psycopg2.extras.execute_values") as mock_execute_values:
            self.db.insert(vectors=vectors, payloads=payloads, ids=ids)
            mock_execute_values.assert_called_once()
            self.db.conn.commit.assert_called_once()

    def test_search(self):
        query_vector = [0.1, 0.2]
        self.db.cur.fetchall.return_value = [
            (str(uuid.uuid4()), 0.1, {"key": "value1"}),
            (str(uuid.uuid4()), 0.2, {"key": "value2"}),
        ]

        results = self.db.search(query=query_vector, limit=2)
        self.db.cur.execute.assert_called_once()

        self.assertEqual(len(results), 2)
        self.assertIsInstance(results[0], OutputData)

    def test_get(self):
        vector_id = str(uuid.uuid4())
        self.db.cur.fetchone.return_value = (vector_id, [0.1, 0.2], {"key": "value1"})

        result = self.db.get(vector_id)
        self.db.cur.execute.assert_called_once_with(
            f"SELECT id, vector, payload FROM test_collection WHERE id = %s",
            (vector_id,),
        )
        self.assertIsInstance(result, OutputData)
        self.assertEqual(result.id, vector_id)

    def test_update(self):
        vector_id = str(uuid.uuid4())
        updated_vector = [0.2, 0.3]
        updated_payload = {"key": "updated_value"}

        self.db.update(vector_id, vector=updated_vector, payload=updated_payload)
        self.db.cur.execute.assert_any_call(
            f"UPDATE test_collection SET vector = %s WHERE id = %s",
            (updated_vector, vector_id),
        )
        self.db.cur.execute.assert_any_call(
            f"UPDATE test_collection SET payload = %s WHERE id = %s",
            (psycopg2.extras.Json(updated_payload), vector_id),
        )
        self.db.conn.commit.assert_called_once()

    def test_delete(self):
        vector_id = str(uuid.uuid4())
        self.db.delete(vector_id)
        self.db.cur.execute.assert_called_once_with(
            f"DELETE FROM test_collection WHERE id = %s", (vector_id,)
        )
        self.db.conn.commit.assert_called_once()

    def test_list_cols(self):
        self.db.cur.fetchall.return_value = [("table1",), ("table2",)]
        result = self.db.list_cols()
        self.db.cur.execute.assert_called_once_with(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"
        )
        self.assertEqual(result, ["table1", "table2"])

    def test_delete_col(self):
        self.db.delete_col()
        self.db.cur.execute.assert_called_once_with(
            f"DROP TABLE IF EXISTS test_collection"
        )
        self.db.conn.commit.assert_called_once()

    def tearDown(self):
        del self.db


if __name__ == "__main__":
    unittest.main()
