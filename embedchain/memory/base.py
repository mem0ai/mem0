import json
import logging
import uuid
from typing import Any, Optional

from embedchain.core.db.database import get_session
from embedchain.core.db.models import ChatHistory as ChatHistoryModel
from embedchain.memory.message import ChatMessage
from embedchain.memory.utils import merge_metadata_dict

logger = logging.getLogger(__name__)


class ChatHistory:
    def __init__(self) -> None:
        self.db_session = get_session()

    def add(self, app_id, session_id, chat_message: ChatMessage) -> Optional[str]:
        memory_id = str(uuid.uuid4())
        metadata_dict = merge_metadata_dict(chat_message.human_message.metadata, chat_message.ai_message.metadata)
        if metadata_dict:
            metadata = self._serialize_json(metadata_dict)
        self.db_session.add(
            ChatHistoryModel(
                app_id=app_id,
                id=memory_id,
                session_id=session_id,
                question=chat_message.human_message.content,
                answer=chat_message.ai_message.content,
                metadata=metadata if metadata_dict else "{}",
            )
        )
        try:
            self.db_session.commit()
        except Exception as e:
            logger.error(f"Error adding chat memory to db: {e}")
            self.db_session.rollback()
            return None

        logger.info(f"Added chat memory to db with id: {memory_id}")
        return memory_id

    def delete(self, app_id: str, session_id: Optional[str] = None):
        """
        Delete all chat history for a given app_id and session_id.
        This is useful for deleting chat history for a given user.

        :param app_id: The app_id to delete chat history for
        :param session_id: The session_id to delete chat history for

        :return: None
        """
        params = {"app_id": app_id}
        if session_id:
            params["session_id"] = session_id
        self.db_session.query(ChatHistoryModel).filter_by(**params).delete()
        try:
            self.db_session.commit()
        except Exception as e:
            logger.error(f"Error deleting chat history: {e}")
            self.db_session.rollback()

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
        params = {"app_id": app_id}
        if not fetch_all:
            params["session_id"] = session_id
        results = (
            self.db_session.query(ChatHistoryModel).filter_by(**params).order_by(ChatHistoryModel.created_at.asc())
        )
        results = results.limit(num_rounds) if not fetch_all else results
        history = []
        for result in results:
            metadata = self._deserialize_json(metadata=result.meta_data or "{}")
            # Return list of dict if display_format is True
            if display_format:
                history.append(
                    {
                        "session_id": result.session_id,
                        "human": result.question,
                        "ai": result.answer,
                        "metadata": result.meta_data,
                        "timestamp": result.created_at,
                    }
                )
            else:
                memory = ChatMessage()
                memory.add_user_message(result.question, metadata=metadata)
                memory.add_ai_message(result.answer, metadata=metadata)
                history.append(memory)
        return history

    def count(self, app_id: str, session_id: Optional[str] = None):
        """
        Count the number of chat messages for a given app_id and session_id.

        :param app_id: The app_id to count chat history for
        :param session_id: The session_id to count chat history for

        :return: The number of chat messages for a given app_id and session_id
        """
        # Rewrite the logic below with sqlalchemy
        params = {"app_id": app_id}
        if session_id:
            params["session_id"] = session_id
        return self.db_session.query(ChatHistoryModel).filter_by(**params).count()

    @staticmethod
    def _serialize_json(metadata: dict[str, Any]):
        return json.dumps(metadata)

    @staticmethod
    def _deserialize_json(metadata: str):
        return json.loads(metadata)

    def close_connection(self):
        self.connection.close()
