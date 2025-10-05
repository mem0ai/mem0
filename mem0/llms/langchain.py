from typing import Dict, List, Optional

from mem0.configs.llms.base import BaseLlmConfig
from mem0.llms.base import LLMBase

try:
    from langchain.chat_models.base import BaseChatModel
    from langchain_core.messages import AIMessage
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

    def _parse_response(self, response: AIMessage, tools: Optional[List[Dict]]):
        """
        Process the response based on whether tools are used or not.

        Args:
            response: AI Message.
            tools: The list of tools provided in the request.

        Returns:
            str or dict: The processed response.
        """
        if not tools:
            return response.content

        processed_response = {
            "content": response.content,
            "tool_calls": [],
        }

        for tool_call in response.tool_calls:
            processed_response["tool_calls"].append(
                {
                    "name": tool_call["name"],
                    "arguments": tool_call["args"],
                }
            )

        return processed_response

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
            tools (list, optional): List of tools that the model can call.
            tool_choice (str, optional): Tool choice method.

        Returns:
            str: The generated response.
        """
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

        langchain_model = self.langchain_model
        if tools:
            langchain_model = langchain_model.bind_tools(tools=tools, tool_choice=tool_choice)

        response: AIMessage = langchain_model.invoke(langchain_messages)
        return self._parse_response(response, tools)
