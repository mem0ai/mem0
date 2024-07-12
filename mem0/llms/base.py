from abc import ABC, abstractmethod


class LLMBase(ABC):
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
