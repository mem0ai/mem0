from abc import ABC, abstractmethod
from typing import Optional

from mem0.configs.llms.base import BaseLlmConfig
from mem0.utils.concurrency import run_in_executor


class LLMBase(ABC):
    def __init__(self, config: Optional[BaseLlmConfig] = None):
        """Initialize a base LLM class

        :param config: LLM configuration option class, defaults to None
        :type config: Optional[BaseLlmConfig], optional
        """
        if config is None:
            self.config = BaseLlmConfig()
        else:
            self.config = config
    
    async def agenerate_response(self, message):
        """Async version of the generate_response method.

        The default implementation delegates to the synchronous generate_response method using
        `run_in_executor`. Subclasses that need to provide a true async implementation
        should override this method to reduce the overhead of using `run_in_executor`.
        """
        return await run_in_executor(
            None,
            self.generate_response,
            message
        )
    
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
