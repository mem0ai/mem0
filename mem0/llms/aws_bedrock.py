import json
from typing import Any, Dict, List, Optional

try:
    import boto3
except ImportError:
    raise ImportError(
        "The 'boto3' library is required. Please install it using 'pip install boto3'."
    )

from mem0.configs.llms.base import BaseLlmConfig
from mem0.llms.base import LLMBase


class AWSBedrockLLM(LLMBase):
    """
    A wrapper for AWS Bedrock's language models, integrating them with the LLMBase class.
    """

    def __init__(self, config: Optional[BaseLlmConfig] = None):
        """
        Initializes the AWS Bedrock LLM with the provided configuration.

        Args:
            config (Optional[BaseLlmConfig]): Configuration object for the model.
        """
        super().__init__(config)

        if not self.config.model:
            self.config.model = "anthropic.claude-3-5-sonnet-20240620-v1:0"
        self.client = boto3.client("bedrock-runtime")
        self.model_kwargs = {
            "temperature": self.config.temperature,
            "max_tokens_to_sample": self.config.max_tokens,
            "top_p": self.config.top_p,
        }

    def _format_messages(self, messages: List[Dict[str, str]]) -> str:
        """
        Formats a list of messages into a structured prompt for the model.

        Args:
            messages (List[Dict[str, str]]): A list of dictionaries containing 'role' and 'content'.

        Returns:
            str: A formatted string combining all messages, structured with roles capitalized and separated by newlines.
        """
        formatted_messages = [
            f"\n\n{msg['role'].capitalize()}: {msg['content']}" for msg in messages
        ]
        return "".join(formatted_messages) + "\n\nAssistant:"

    def _parse_response(self, response) -> str:
        """
        Extracts the generated response from the API response.

        Args:
            response: The raw response from the AWS Bedrock API.

        Returns:
            str: The generated response text.
        """
        response_body = json.loads(response["body"].read().decode())
        return response_body.get("completion", "")

    def _prepare_input(
        self,
        provider: str,
        model: str,
        prompt: str,
        model_kwargs: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Prepares the input dictionary for the specified provider's model.

        Args:
            provider (str): The model provider (e.g., "meta", "ai21", "mistral", "cohere", "amazon").
            model (str): The model identifier.
            prompt (str): The input prompt.
            model_kwargs (Optional[Dict[str, Any]]): Additional model parameters.

        Returns:
            Dict[str, Any]: The prepared input dictionary.
        """
        model_kwargs = model_kwargs or {}
        input_body = {"prompt": prompt, **model_kwargs}

        provider_mappings = {
            "meta": {"max_tokens_to_sample": "max_gen_len"},
            "ai21": {"max_tokens_to_sample": "maxTokens", "top_p": "topP"},
            "mistral": {"max_tokens_to_sample": "max_tokens"},
            "cohere": {"max_tokens_to_sample": "max_tokens", "top_p": "p"},
        }

        if provider in provider_mappings:
            for old_key, new_key in provider_mappings[provider].items():
                if old_key in input_body:
                    input_body[new_key] = input_body.pop(old_key)

        if provider == "cohere" and "cohere.command-r" in model:
            input_body["message"] = input_body.pop("prompt")

        if provider == "amazon":
            input_body = {
                "inputText": prompt,
                "textGenerationConfig": {
                    "maxTokenCount": model_kwargs.get("max_tokens_to_sample"),
                    "topP": model_kwargs.get("top_p"),
                    "temperature": model_kwargs.get("temperature"),
                },
            }
            input_body["textGenerationConfig"] = {
                k: v
                for k, v in input_body["textGenerationConfig"].items()
                if v is not None
            }

        return input_body

    def generate_response(self, messages: List[Dict[str, str]]) -> str:
        """
        Generates a response using AWS Bedrock based on the provided messages.

        Args:
            messages (List[Dict[str, str]]): List of message dictionaries containing 'role' and 'content'.

        Returns:
            str: The generated response text.
        """
        prompt = self._format_messages(messages)
        provider = self.config.model.split(".")[0]
        input_body = self._prepare_input(
            provider, self.config.model, prompt, self.model_kwargs
        )
        body = json.dumps(input_body)

        response = self.client.invoke_model(
            body=body,
            modelId=self.config.model,
            accept="application/json",
            contentType="application/json",
        )

        return self._parse_response(response)
