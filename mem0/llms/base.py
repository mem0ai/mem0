from typing import Optional, Dict
from abc import ABC, abstractmethod

from mem0.configs.llms.base import BaseLlmConfig


class LLMBase(ABC):
    def __init__(self, configDict: Optional[Dict] = None):
        """Initialize a base LLM class

        :param config: LLM configuration option class, defaults to None
        :type config: Optional[BaseLlmConfig], optional
        """
        if configDict is None:
            self.config = BaseLlmConfig()
        else:
            self.config = BaseLlmConfig(**configDict)

    @abstractmethod
    def generate_response(self, messages):
        """
        Generate a response based on the given messages.

        Args:
            messages (list): List of message dicts containing 'role' and 'content'.

        Returns:
            str: The generated response.
        """
        pass
