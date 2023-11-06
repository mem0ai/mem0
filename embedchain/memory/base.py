import json
import logging
import sqlite3
import time
import uuid
from typing import Any, Dict, List, Optional

from embedchain.constants import SQLITE_PATH
from embedchain.memory.message import ECBaseChatMessage
from embedchain.memory.utils import merge_metadata_dict

"""
app_id: saves the app_id of the embedchain app.
id: saves the id of the dialogue between user and model.
question: user query
answer: ai response
created_at: unix formatted timestamp of creation.
metadata: stringified JSON of metadata dictionary.
"""
CHAT_MEMORY_CREATE_TABLE_QUERY = """
            CREATE TABLE IF NOT EXISTS chat_memory (
                app_id TEXT,
                id TEXT,
                question TEXT,
                answer TEXT,
                created_at REAL,
                metadata TEXT,
                PRIMARY KEY (id, app_id)
            )
            """


class ECChatMemory:
    def __init__(self) -> None:
        with sqlite3.connect(SQLITE_PATH) as self.connection:
            self.cursor = self.connection.cursor()

            self.cursor.execute(CHAT_MEMORY_CREATE_TABLE_QUERY)
            self.connection.commit()

    def add(self, app_id, chat_memory: ECBaseChatMessage) -> Optional[str]:
        memory_id = str(uuid.uuid4())
        created_at = time.time()
        metadata = self._serialize_json(
            merge_metadata_dict(chat_memory.human_message.metadata, chat_memory.ai_message.metadata)
        )
        ADD_CHAT_MESSAGE_QUERY = """
            INSERT INTO chat_memory (app_id, id, question, answer, created_at, metadata)
            VALUES (?, ?, ?, ?, ?, ?)
        """
        self.cursor.execute(
            ADD_CHAT_MESSAGE_QUERY,
            (
                app_id,
                memory_id,
                chat_memory.human_message.content,
                chat_memory.ai_message.content,
                created_at,
                metadata,
            ),
        )
        self.connection.commit()
        logging.info(f"Added chat memory to db with id: {memory_id}")
        return memory_id

    def delete_chat_history(self, app_id: str):
        DELETE_CHAT_HISTORY_QUERY = """
            DELETE FROM chat_memory WHERE app_id=?
        """
        self.cursor.execute(
            DELETE_CHAT_HISTORY_QUERY,
            (app_id,),
        )
        self.connection.commit()

    def get_recent_memories(self, app_id, n_memories=10) -> List[ECBaseChatMessage]:
        """
        Get the most recent n_memories number of memories
        for a given app_id.
        """

        QUERY = """
            SELECT * FROM chat_memory
            WHERE app_id=?
            ORDER BY created_at DESC
            LIMIT ?
        """
        self.cursor.execute(
            QUERY,
            (app_id, n_memories),
        )

        results = self.cursor.fetchall()
        memories = []
        for result in results:
            app_id, id, question, answer, timestamp, metadata = result
            metadata = self._deserialize_json(metadata=metadata)
            memory = ECBaseChatMessage()
            memory.add_user_message(question, metadata=metadata)
            memory.add_ai_message(answer, metadata=metadata)
            memories.append(memory)
        return memories

    def _serialize_json(self, metadata: Dict[str, Any]):
        return json.dumps(metadata)

    def _deserialize_json(self, metadata: str):
        return json.loads(metadata)

    def close_connection(self):
        self.connection.close()

    def count_chat_memory_entries(self, app_id: str):
        QUERY = """
        SELECT COUNT(*) FROM chat_memory
        WHERE app_id=?
        """
        self.cursor.execute(
            QUERY,
            (app_id,),
        )
        count = self.cursor.fetchone()[0]
        return count
