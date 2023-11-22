import logging
from typing import Any, Dict, Optional

from embedchain.helpers.json_serializable import JSONSerializable


class BaseMessage(JSONSerializable):
    """
    The base abstract message class.

    Messages are the inputs and outputs of Models.
    """

    # The string content of the message.
    content: str

    # The creator of the message. AI, Human, Bot etc.
    by: str

    # Any additional info.
    metadata: Dict[str, Any]

    def __init__(self, content: str, creator: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        super().__init__()
        self.content = content
        self.creator = creator
        self.metadata = metadata

    @property
    def type(self) -> str:
        """Type of the Message, used for serialization."""

    @classmethod
    def is_lc_serializable(cls) -> bool:
        """Return whether this class is serializable."""
        return True

    def __str__(self) -> str:
        return f"{self.creator}: {self.content}"


class ChatMessage(JSONSerializable):
    """
    The base abstract chat message class.

    Chat messages are the pair of (question, answer) conversation
    between human and model.
    """

    human_message: Optional[BaseMessage] = None
    ai_message: Optional[BaseMessage] = None

    def add_user_message(self, message: str, metadata: Optional[dict] = None):
        if self.human_message:
            logging.info(
                "Human message already exists in the chat message,\
                overwritting it with new message."
            )

        self.human_message = BaseMessage(content=message, creator="human", metadata=metadata)

    def add_ai_message(self, message: str, metadata: Optional[dict] = None):
        if self.ai_message:
            logging.info(
                "AI message already exists in the chat message,\
                overwritting it with new message."
            )

        self.ai_message = BaseMessage(content=message, creator="ai", metadata=metadata)

    def __str__(self) -> str:
        return f"{self.human_message}\n{self.ai_message}"
