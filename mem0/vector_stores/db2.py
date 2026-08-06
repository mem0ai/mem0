import json
import logging
from typing import Any, List, Optional

from pydantic import BaseModel

from mem0.vector_stores.base import VectorStoreBase

logger = logging.getLogger(__name__)

class OutputData(BaseModel):
    id: Optional[str]
    score: Optional[float]
    payload: Optional[dict]

class Db2VectorStore(VectorStoreBase):
    def __init__(
        self,
        connection_params: Optional[dict] = None,
        client: Optional[Any] = None,
        table_name: str = "mem0",
        id_field: str = "id",
        text_field: str = "text",
        metadata_field: str = "metadata",
        embedding_field: str = "embedding",
        distance_strategy: str = "COSINE",
        **kwargs
    ):
        try:
            import ibm_db
            import ibm_db_dbi
            self.ibm_db = ibm_db
            self.ibm_db_dbi = ibm_db_dbi
        except ImportError:
            raise ImportError(
                "The 'ibm_db' library is required to use the Db2 vector store. "
                "Please install it using 'pip install ibm_db'."
            )

        self.table_name = table_name
        self.id_field = id_field
        self.text_field = text_field
        self.metadata_field = metadata_field
        self.embedding_field = embedding_field
        self.distance_strategy = distance_strategy.upper()

        if client is not None:
            self.conn = client
        elif connection_params is not None:
            conn_string = connection_params.get("connection_string")
            if not conn_string:
                ssl_part = "Security=SSL;" if connection_params.get("ssl") else ""
                conn_string = (
                    f"DATABASE={connection_params.get('database')};"
                    f"HOSTNAME={connection_params.get('host')};"
                    f"PORT={connection_params.get('port', 50000)};"
                    f"PROTOCOL=TCPIP;"
                    f"UID={connection_params.get('username')};"
                    f"PWD={connection_params.get('password')};"
                    f"{ssl_part}"
                )
            self.conn = self.ibm_db_dbi.connect(conn_string, "", "")
        else:
            raise ValueError("Either 'client' or 'connection_params' must be provided.")

        self._collection_ensured = False

    def _ensure_collection(self, vector_size: int = 1536):
        if self._collection_ensured:
            return
        collections = self.list_cols()
        if self.table_name not in collections:
            self.create_col(self.table_name, vector_size, self.distance_strategy)
        self._collection_ensured = True

    def create_col(self, name: str, vector_size: int, distance: str):
        cursor = self.conn.cursor()
        try:
            query = f"""
                CREATE TABLE {name} (
                    {self.id_field} VARCHAR(255) NOT NULL PRIMARY KEY,
                    {self.embedding_field} VECTOR({vector_size}, FLOAT32),
                    {self.metadata_field} CLOB
                )
            """
            cursor.execute(query)
            self.conn.commit()
        except Exception as e:
            self.conn.rollback()
            raise e
        finally:
            cursor.close()

    def insert(self, vectors: List[List[float]], payloads: Optional[List[dict]] = None, ids: Optional[List[str]] = None):
        if not vectors:
            return

        vector_size = len(vectors[0])
        self._ensure_collection(vector_size=vector_size)

        cursor = self.conn.cursor()
        try:
            query = f"""
                INSERT INTO {self.table_name} ({self.id_field}, {self.embedding_field}, {self.metadata_field})
                VALUES (?, SYSTOOLS.JSON2BSON(?), ?)
            """
            # In DB2, we can insert vector as string using cast, but here we can just pass array as string '[1,2,3]' 
            # and let DB2 implicitly cast or use 'cast(? as vector(n, float32))'
            # Let's use CAST
            query = f"""
                INSERT INTO {self.table_name} ({self.id_field}, {self.embedding_field}, {self.metadata_field})
                VALUES (?, CAST(? AS VECTOR({vector_size}, FLOAT32)), ?)
            """
            
            for i in range(len(vectors)):
                v_id = ids[i] if ids else str(i)
                v_str = json.dumps(vectors[i])
                p_str = json.dumps(payloads[i]) if payloads and payloads[i] else "{}"
                cursor.execute(query, (v_id, v_str, p_str))
                
            self.conn.commit()
        except Exception as e:
            self.conn.rollback()
            raise e
        finally:
            cursor.close()

    def _build_filters(self, filters: dict) -> tuple[str, list]:
        if not filters:
            return "", []

        conditions = []
        params = []

        for key, value in filters.items():
            json_path = f"$.\"{key}\""
            
            if value == "*":
                # Check for existence
                conditions.append(f"JSON_EXISTS({self.metadata_field}, 'strict {json_path}') = 'TRUE'")
            elif isinstance(value, dict) and "in" in value:
                in_values = value["in"]
                placeholders = ", ".join(["?"] * len(in_values))
                conditions.append(f"JSON_VALUE({self.metadata_field}, 'strict {json_path}') IN ({placeholders})")
                params.extend([str(v) for v in in_values])
            elif isinstance(value, list):
                placeholders = ", ".join(["?"] * len(value))
                conditions.append(f"JSON_VALUE({self.metadata_field}, 'strict {json_path}') IN ({placeholders})")
                params.extend([str(v) for v in value])
            else:
                conditions.append(f"JSON_VALUE({self.metadata_field}, 'strict {json_path}') = ?")
                params.append(str(value))

        return " AND ".join(conditions), params

    def search(self, query: str, vectors: List[float], top_k: int = 5, filters: Optional[dict] = None) -> List[OutputData]:
        if not vectors:
            return []
            
        vector_size = len(vectors)
        self._ensure_collection(vector_size=vector_size)
        
        filter_sql, filter_params = self._build_filters(filters)
        where_clause = f"WHERE {filter_sql}" if filter_sql else ""

        db2_metric = self.distance_strategy
        if db2_metric == "DOT":
            db2_metric = "DOT_PRODUCT"

        vector_str = json.dumps(vectors)
        
        query_sql = f"""
            SELECT {self.id_field}, {self.metadata_field}, 
                   VECTOR_DISTANCE({self.embedding_field}, CAST(? AS VECTOR({vector_size}, FLOAT32)), '{db2_metric}') as dist
            FROM {self.table_name}
            {where_clause}
            ORDER BY dist ASC
            LIMIT ?
        """

        cursor = self.conn.cursor()
        try:
            params = (vector_str,) + tuple(filter_params) + (top_k,)
            cursor.execute(query_sql, params)
            
            results = []
            for row in cursor.fetchall():
                v_id, metadata_str, dist = row[0], row[1], float(row[2])
                
                # Convert distance to similarity
                if self.distance_strategy == "COSINE":
                    score = max(0.0, 1.0 - dist)
                elif self.distance_strategy == "EUCLIDEAN":
                    score = 1.0 / (1.0 + dist)
                elif self.distance_strategy == "DOT":
                    score = dist
                else:
                    score = dist
                    
                payload = json.loads(metadata_str) if metadata_str else {}
                results.append(OutputData(id=str(v_id), score=score, payload=payload))
                
            return results
        finally:
            cursor.close()

    def delete(self, vector_id: str):
        self._ensure_collection()
        cursor = self.conn.cursor()
        try:
            cursor.execute(f"DELETE FROM {self.table_name} WHERE {self.id_field} = ?", (vector_id,))
            self.conn.commit()
        except Exception as e:
            self.conn.rollback()
            raise e
        finally:
            cursor.close()

    def update(self, vector_id: str, vector: Optional[List[float]] = None, payload: Optional[dict] = None):
        self._ensure_collection()
        cursor = self.conn.cursor()
        try:
            if vector is not None and payload is not None:
                vector_size = len(vector)
                query = f"""
                    UPDATE {self.table_name} 
                    SET {self.embedding_field} = CAST(? AS VECTOR({vector_size}, FLOAT32)),
                        {self.metadata_field} = ?
                    WHERE {self.id_field} = ?
                """
                cursor.execute(query, (json.dumps(vector), json.dumps(payload), vector_id))
            elif vector is not None:
                vector_size = len(vector)
                query = f"""
                    UPDATE {self.table_name} 
                    SET {self.embedding_field} = CAST(? AS VECTOR({vector_size}, FLOAT32))
                    WHERE {self.id_field} = ?
                """
                cursor.execute(query, (json.dumps(vector), vector_id))
            elif payload is not None:
                query = f"""
                    UPDATE {self.table_name} 
                    SET {self.metadata_field} = ?
                    WHERE {self.id_field} = ?
                """
                cursor.execute(query, (json.dumps(payload), vector_id))
            self.conn.commit()
        except Exception as e:
            self.conn.rollback()
            raise e
        finally:
            cursor.close()

    def get(self, vector_id: str) -> Optional[OutputData]:
        self._ensure_collection()
        cursor = self.conn.cursor()
        try:
            query = f"SELECT {self.id_field}, {self.metadata_field} FROM {self.table_name} WHERE {self.id_field} = ?"
            cursor.execute(query, (vector_id,))
            row = cursor.fetchone()
            if row:
                v_id, metadata_str = row[0], row[1]
                payload = json.loads(metadata_str) if metadata_str else {}
                return OutputData(id=str(v_id), score=None, payload=payload)
            return None
        finally:
            cursor.close()

    def list_cols(self) -> List[str]:
        cursor = self.conn.cursor()
        try:
            # Query SYSCAT.TABLES for DB2
            cursor.execute(f"SELECT TABNAME FROM SYSCAT.TABLES WHERE TABSCHEMA = CURRENT SCHEMA")
            return [row[0].upper() for row in cursor.fetchall()]
        except:
            # Fallback for some configurations or other DB2 flavors
            try:
                cursor.execute(f"SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA = CURRENT_SCHEMA")
                return [row[0].upper() for row in cursor.fetchall()]
            except:
                return []
        finally:
            cursor.close()

    def delete_col(self):
        cursor = self.conn.cursor()
        try:
            cursor.execute(f"DROP TABLE {self.table_name}")
            self.conn.commit()
        except Exception:
            self.conn.rollback()
        finally:
            cursor.close()

    def col_info(self) -> dict:
        self._ensure_collection()
        cursor = self.conn.cursor()
        try:
            cursor.execute(f"SELECT COUNT(*) FROM {self.table_name}")
            row = cursor.fetchone()
            count = row[0] if row else 0
            return {"name": self.table_name, "count": count}
        finally:
            cursor.close()

    def list(self, filters: Optional[dict] = None, top_k: int = 100) -> List[OutputData]:
        self._ensure_collection()
        filter_sql, filter_params = self._build_filters(filters)
        where_clause = f"WHERE {filter_sql}" if filter_sql else ""
        
        query_sql = f"""
            SELECT {self.id_field}, {self.metadata_field}
            FROM {self.table_name}
            {where_clause}
            LIMIT ?
        """

        cursor = self.conn.cursor()
        try:
            params = tuple(filter_params) + (top_k,)
            cursor.execute(query_sql, params)
            
            results = []
            for row in cursor.fetchall():
                v_id, metadata_str = row[0], row[1]
                payload = json.loads(metadata_str) if metadata_str else {}
                results.append(OutputData(id=str(v_id), score=None, payload=payload))
            return results
        finally:
            cursor.close()

    def reset(self):
        self.delete_col()
        self._collection_ensured = False
