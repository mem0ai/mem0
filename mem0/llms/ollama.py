import ollama
from llm.base import LLMBase


class OllamaLLM(LLMBase):
    def __init__(self, model="llama3"):
        self.model = model
        self._ensure_model_exists()

    def _ensure_model_exists(self):
        """
        Ensure the specified model exists locally. If not, pull it from Ollama.
        """
        model_list = [m["name"] for m in ollama.list()["models"]]
        if not any(m.startswith(self.model) for m in model_list):
            ollama.pull(self.model)

    def generate_response(self, messages):
        """
        Generate a response based on the given messages using Ollama.

        Args:
            messages (list): List of message dicts containing 'role' and 'content'.

        Returns:
            str: The generated response.
        """
        response = ollama.chat(model=self.model, messages=messages)
        return response["message"]["content"]
