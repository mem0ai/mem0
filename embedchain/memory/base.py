import json
import logging
import sqlite3
import uuid
from typing import Any, Optional

from embedchain.constants import SQLITE_PATH
from embedchain.memory.message import ChatMessage
from embedchain.memory.utils import merge_metadata_dict

CHAT_MESSAGE_CREATE_TABLE_QUERY = """
    CREATE TABLE IF NOT EXISTS ec_chat_history (
        app_id TEXT,
        id TEXT,
        session_id TEXT,
        question TEXT,
        answer TEXT,
        metadata TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (id, app_id, session_id)
    )
"""


class ChatHistory:
    def __init__(self) -> None:
        with sqlite3.connect(SQLITE_PATH, check_same_thread=False) as self.connection:
            self.cursor = self.connection.cursor()
            self.cursor.execute(CHAT_MESSAGE_CREATE_TABLE_QUERY)
            self.connection.commit()

    def add(self, app_id, session_id, chat_message: ChatMessage) -> Optional[str]:
        memory_id = str(uuid.uuid4())
        metadata_dict = merge_metadata_dict(chat_message.human_message.metadata, chat_message.ai_message.metadata)
        if metadata_dict:
            metadata = self._serialize_json(metadata_dict)
        ADD_CHAT_MESSAGE_QUERY = """
            INSERT INTO ec_chat_history (app_id, id, session_id, question, answer, metadata)
            VALUES (?, ?, ?, ?, ?, ?)
        """
        self.cursor.execute(
            ADD_CHAT_MESSAGE_QUERY,
            (
                app_id,
                memory_id,
                session_id,
                chat_message.human_message.content,
                chat_message.ai_message.content,
                metadata if metadata_dict else "{}",
            ),
        )
        self.connection.commit()
        logging.info(f"Added chat memory to db with id: {memory_id}")
        return memory_id

    def delete(self, app_id: str, session_id: Optional[str] = None):
        """
        Delete all chat history for a given app_id and session_id.
        This is useful for deleting chat history for a given user.

        :param app_id: The app_id to delete chat history for
        :param session_id: The session_id to delete chat history for

        :return: None
        """
        if session_id:
            DELETE_CHAT_HISTORY_QUERY = "DELETE FROM ec_chat_history WHERE app_id=? AND session_id=?"
            params = (app_id, session_id)
        else:
            DELETE_CHAT_HISTORY_QUERY = "DELETE FROM ec_chat_history WHERE app_id=?"
            params = (app_id,)

        self.cursor.execute(DELETE_CHAT_HISTORY_QUERY, params)
        self.connection.commit()

    def get(
        self, app_id, session_id: str = "default", num_rounds=10, fetch_all: bool = False, display_format=False
    ) -> list[ChatMessage]:
        """
        Get the chat history for a given app_id.

        param: app_id - The app_id to get chat history
        param: session_id (optional) - The session_id to get chat history. Defaults to "default"
        param: num_rounds (optional) - The number of rounds to get chat history. Defaults to 10
        param: fetch_all (optional) - Whether to fetch all chat history or not. Defaults to False
        param: display_format (optional) - Whether to return the chat history in display format. Defaults to False
        """

        base_query = """
            SELECT * FROM ec_chat_history
            WHERE app_id=?
        """

        if fetch_all:
            additional_query = "ORDER BY created_at DESC"
            params = (app_id,)
        else:
            additional_query = """
                AND session_id=?
                ORDER BY created_at DESC
                LIMIT ?
            """
            params = (app_id, session_id, num_rounds)

        QUERY = base_query + additional_query

        self.cursor.execute(
            QUERY,
            params,
        )

        results = self.cursor.fetchall()
        history = []
        for result in results:
            app_id, _, session_id, question, answer, metadata, timestamp = result
            metadata = self._deserialize_json(metadata=metadata)
            # Return list of dict if display_format is True
            if display_format:
                history.append(
                    {
                        "session_id": session_id,
                        "human": question,
                        "ai": answer,
                        "metadata": metadata,
                        "timestamp": timestamp,
                    }
                )
            else:
                memory = ChatMessage()
                memory.add_user_message(question, metadata=metadata)
                memory.add_ai_message(answer, metadata=metadata)
                history.append(memory)
        return history

    def count(self, app_id: str, session_id: Optional[str] = None):
        """
        Count the number of chat messages for a given app_id and session_id.

        :param app_id: The app_id to count chat history for
        :param session_id: The session_id to count chat history for

        :return: The number of chat messages for a given app_id and session_id
        """
        if session_id:
            QUERY = "SELECT COUNT(*) FROM ec_chat_history WHERE app_id=? AND session_id=?"
            params = (app_id, session_id)
        else:
            QUERY = "SELECT COUNT(*) FROM ec_chat_history WHERE app_id=?"
            params = (app_id,)

        self.cursor.execute(QUERY, params)
        count = self.cursor.fetchone()[0]
        return count

    @staticmethod
    def _serialize_json(metadata: dict[str, Any]):
        return json.dumps(metadata)

    @staticmethod
    def _deserialize_json(metadata: str):
        return json.loads(metadata)

    def close_connection(self):
        self.connection.close()
