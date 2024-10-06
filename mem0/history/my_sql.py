from datetime import datetime
from typing import Optional, Union
from urllib.parse import urlparse
import uuid
try:
    import mysql.connector
    from mysql.connector.pooling import PooledMySQLConnection
    from mysql.connector.abstracts import MySQLConnectionAbstract
except ImportError:
    raise ImportError(
        "The 'mysql' library is required. "
        "Please install it using 'pip install mysql-connector-python'."
    )

from mem0.history.base import HistoryDBBase


class Mysql(HistoryDBBase):
    def __init__(
        self,
        conn: Optional[Union[PooledMySQLConnection, MySQLConnectionAbstract]] = None,
        url: Optional[str] = None,
        host: Optional[str] = None,
        user: Optional[str] = None,
        password: Optional[str] = None,
        database: Optional[str] = None,
        port: Optional[int] = 3306,
    ):
        super().__init__()
        if conn:
            self.conn = conn
        elif url:
            _url = urlparse(url)
            config = {
                "user": _url.username,
                "password": _url.password,
                "host": _url.hostname,
                "database": _url.path[1:],
                "port": _url.port,
                "raise_on_warnings": True,
            }
            self.conn = mysql.connector.connect(**config)
        else:
            config = {
                "user": user,
                "password": password,
                "host": host,
                "database": database,
                "port": port,
                "raise_on_warnings": True,
            }
            self.conn = mysql.connector.connect(**config)
        self._create_history_table()
    
    def _create_history_table(self):
        with self.conn.cursor() as cursor:
            cursor.execute("SHOW TABLES LIKE 'mem_history'")
            if cursor.fetchone():
                return
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS mem_history (
                    id VARCHAR(255) PRIMARY KEY,
                    memory_id VARCHAR(255),
                    old_memory TEXT,
                    new_memory TEXT,
                    new_value TEXT,
                    event VARCHAR(255),
                    created_at TIMESTAMP NOT NULL,
                    updated_at TIMESTAMP NOT NULL,
                    is_deleted TINYINT
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
                """
            )

    def add_history(
        self,
        memory_id: str,
        old_memory: str,
        new_memory: str,
        event: str,
        created_at=None,
        updated_at=None,
        is_deleted=0,
    ):
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO mem_history
                (id, memory_id, old_memory, new_memory, event, created_at, updated_at, is_deleted)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    str(uuid.uuid4()),
                    memory_id,
                    old_memory,
                    new_memory,
                    event,
                    created_at,
                    updated_at,
                    is_deleted,
                ),
            )
        self.conn.commit()
        
    def get_history(self, memory_id):
        with self.conn.cursor(dictionary=True) as cursor:
            cursor.execute(
                """
                SELECT id, memory_id, old_memory, new_memory, event, created_at, updated_at
                FROM mem_history
                WHERE memory_id = %s
                ORDER BY updated_at ASC
                """,
                (memory_id,)
            )
            return cursor.fetchall()

    def reset(self):
        with self.conn.cursor() as cursor:
            cursor.execute("DROP TABLE IF EXISTS mem_history")
        self.conn.commit()

    