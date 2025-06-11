from typing import Dict, List, Optional

from mem0.configs.llms.base import BaseLlmConfig
from mem0.llms.base import LLMBase

try:
    from langchain.chat_models.base import BaseChatModel
except ImportError:
    raise ImportError("langchain is not installed. Please install it using `pip install langchain`")


class LangchainLLM(LLMBase):
    def __init__(self, config: Optional[BaseLlmConfig] = None):
        super().__init__(config)

        if self.config.model is None:
            raise ValueError("`model` parameter is required")

        if not isinstance(self.config.model, BaseChatModel):
            raise ValueError("`model` must be an instance of BaseChatModel")

        self.langchain_model = self.config.model

    def generate_response(
        self,
        messages: List[Dict[str, str]],
        response_format=None,
        tools: Optional[List[Dict]] = None,
        tool_choice: str = "auto",
    ):
        """
        Generate a response based on the given messages using langchain_community.

        Args:
            messages (list): List of message dicts containing 'role' and 'content'.
            response_format (str or object, optional): Format of the response. Not used in Langchain.
            tools (list, optional): List of tools that the model can call. Not used in Langchain.
            tool_choice (str, optional): Tool choice method. Not used in Langchain.

        Returns:
            str: The generated response.
        """
        try:
            # Convert the messages to LangChain's tuple format
            langchain_messages = []
            for message in messages:
                role = message["role"]
                content = message["content"]

                if role == "system":
                    langchain_messages.append(("system", content))
                elif role == "user":
                    langchain_messages.append(("human", content))
                elif role == "assistant":
                    langchain_messages.append(("ai", content))

            if not langchain_messages:
                raise ValueError("No valid messages found in the messages list")

            ai_message = self.langchain_model.invoke(langchain_messages)

            return ai_message.content

        except Exception as e:
            raise Exception(f"Error generating response using langchain model: {str(e)}")
