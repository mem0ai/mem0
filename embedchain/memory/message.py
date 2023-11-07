import logging
from typing import Any, Dict, Optional

from embedchain.helper.json_serializable import JSONSerializable


class BaseMessage(JSONSerializable):
    """
    The base abstract message class.

    Messages are the inputs and outputs of Models.
    """

    content: str
    """The string content of the message."""

    by: str
    """The creator of the message. AI, Human, Bot etc."""

    metadata: Dict[str, Any]
    """Any additional info."""

    def __init__(self, content: str, by: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        super().__init__()
        self.content = content
        self.by = by
        self.metadata = metadata

    @property
    def type(self) -> str:
        """Type of the Message, used for serialization."""

    @classmethod
    def is_lc_serializable(cls) -> bool:
        """Return whether this class is serializable."""
        return True

    def __str__(self) -> str:
        return f"{self.by}: {self.content}"


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

        self.human_message = BaseMessage(content=message, by="human", metadata=metadata)

    def add_ai_message(self, message: str, metadata: Optional[dict] = None):
        if self.ai_message:
            logging.info(
                "AI message already exists in the chat message,\
                overwritting it with new message."
            )

        self.ai_message = BaseMessage(content=message, by="ai", metadata=metadata)

    def __str__(self) -> str:
        return f"{self.human_message} | {self.ai_message}"
