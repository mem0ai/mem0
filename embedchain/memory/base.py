import json
import logging
import sqlite3
import uuid
from typing import Any, Dict, List, Optional

from embedchain.constants import SQLITE_PATH
from embedchain.memory.message import ChatMessage
from embedchain.memory.utils import merge_metadata_dict

CHAT_MESSAGE_CREATE_TABLE_QUERY = """
            CREATE TABLE IF NOT EXISTS chat_history (
                app_id TEXT,
                id TEXT,
                question TEXT,
                answer TEXT,
                metadata TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (id, app_id)
            )
            """


class ECChatMemory:
    def __init__(self) -> None:
        with sqlite3.connect(SQLITE_PATH) as self.connection:
            self.cursor = self.connection.cursor()

            self.cursor.execute(CHAT_MESSAGE_CREATE_TABLE_QUERY)
            self.connection.commit()

    def add(self, app_id, chat_message: ChatMessage) -> Optional[str]:
        memory_id = str(uuid.uuid4())
        metadata_dict = merge_metadata_dict(chat_message.human_message.metadata, chat_message.ai_message.metadata)
        if metadata_dict:
            metadata = self._serialize_json(metadata_dict)
        ADD_CHAT_MESSAGE_QUERY = """
            INSERT INTO chat_history (app_id, id, question, answer, metadata)
            VALUES (?, ?, ?, ?, ?)
        """
        self.cursor.execute(
            ADD_CHAT_MESSAGE_QUERY,
            (
                app_id,
                memory_id,
                chat_message.human_message.content,
                chat_message.ai_message.content,
                metadata if metadata_dict else "{}",
            ),
        )
        self.connection.commit()
        logging.info(f"Added chat memory to db with id: {memory_id}")
        return memory_id

    def delete_chat_history(self, app_id: str):
        DELETE_CHAT_HISTORY_QUERY = """
            DELETE FROM chat_history WHERE app_id=?
        """
        self.cursor.execute(
            DELETE_CHAT_HISTORY_QUERY,
            (app_id,),
        )
        self.connection.commit()

    def get_recent_memories(self, app_id, num_rounds=10, display_format=False) -> List[ChatMessage]:
        """
        Get the most recent num_rounds rounds of conversations
        between human and AI, for a given app_id.
        """

        QUERY = """
            SELECT * FROM chat_history
            WHERE app_id=?
            ORDER BY created_at DESC
            LIMIT ?
        """
        self.cursor.execute(
            QUERY,
            (app_id, num_rounds),
        )

        results = self.cursor.fetchall()
        history = []
        for result in results:
            app_id, _, question, answer, metadata, timestamp = result
            metadata = self._deserialize_json(metadata=metadata)
            # Return list of dict if display_format is True
            if display_format:
                history.append({"human": question, "ai": answer, "metadata": metadata, "timestamp": timestamp})
            else:
                memory = ChatMessage()
                memory.add_user_message(question, metadata=metadata)
                memory.add_ai_message(answer, metadata=metadata)
                history.append(memory)
        return history

    def _serialize_json(self, metadata: Dict[str, Any]):
        return json.dumps(metadata)

    def _deserialize_json(self, metadata: str):
        return json.loads(metadata)

    def close_connection(self):
        self.connection.close()

    def count_history_messages(self, app_id: str):
        QUERY = """
        SELECT COUNT(*) FROM chat_history
        WHERE app_id=?
        """
        self.cursor.execute(
            QUERY,
            (app_id,),
        )
        count = self.cursor.fetchone()[0]
        return count
