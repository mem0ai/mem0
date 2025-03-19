import json
from typing import Any, Dict, List, Optional

try:
    import boto3
except ImportError:
    raise ImportError("The 'boto3' library is required. Please install it using 'pip install boto3'.")

from mem0.configs.llms.base import BaseLlmConfig
from mem0.llms.base import LLMBase


class AWSBedrockLLM(LLMBase):
    def __init__(self, config: Optional[BaseLlmConfig] = None):
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
        Formats a list of messages into the required prompt structure for the model.

        Args:
            messages (List[Dict[str, str]]): A list of dictionaries where each dictionary represents a message.
                                            Each dictionary contains 'role' and 'content' keys.

        Returns:
            str: A formatted string combining all messages, structured with roles capitalized and separated by newlines.
        """
        formatted_messages = []
        for message in messages:
            role = message["role"].capitalize()
            content = message["content"]
            formatted_messages.append(f"\n\n{role}: {content}")

        return "".join(formatted_messages) + "\n\nAssistant:"

    def _parse_response(self, response, tools) -> str:
        """
        Process the response based on whether tools are used or not.

        Args:
            response: The raw response from API.
            tools: The list of tools provided in the request.

        Returns:
            str or dict: The processed response.
        """
        if tools:
            processed_response = {"tool_calls": []}

            if response["output"]["message"]["content"]:
                for item in response["output"]["message"]["content"]:
                    if "toolUse" in item:
                        processed_response["tool_calls"].append(
                            {
                                "name": item["toolUse"]["name"],
                                "arguments": item["toolUse"]["input"],
                            }
                        )

            return processed_response

        response_body = json.loads(response["body"].read().decode())
        return response_body.get("completion", "")

    def _prepare_input(
        self,
        provider: str,
        model: str,
        prompt: str,
        model_kwargs: Optional[Dict[str, Any]] = {},
    ) -> Dict[str, Any]:
        """
        Prepares the input dictionary for the specified provider's model by mapping and renaming
        keys in the input based on the provider's requirements.

        Args:
            provider (str): The name of the service provider (e.g., "meta", "ai21", "mistral", "cohere", "amazon").
            model (str): The name or identifier of the model being used.
            prompt (str): The text prompt to be processed by the model.
            model_kwargs (Dict[str, Any]): Additional keyword arguments specific to the model's requirements.

        Returns:
            Dict[str, Any]: The prepared input dictionary with the correct keys and values for the specified provider.
        """

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
                k: v for k, v in input_body["textGenerationConfig"].items() if v is not None
            }

        return input_body

    def _convert_tool_format(self, original_tools):
        """
        Converts a list of tools from their original format to a new standardized format.

        Args:
            original_tools (list): A list of dictionaries representing the original tools, each containing a 'type' key and corresponding details.

        Returns:
            list: A list of dictionaries representing the tools in the new standardized format.
        """
        new_tools = []

        for tool in original_tools:
            if tool["type"] == "function":
                function = tool["function"]
                new_tool = {
                    "toolSpec": {
                        "name": function["name"],
                        "description": function["description"],
                        "inputSchema": {
                            "json": {
                                "type": "object",
                                "properties": {},
                                "required": function["parameters"].get("required", []),
                            }
                        },
                    }
                }

                for prop, details in function["parameters"].get("properties", {}).items():
                    new_tool["toolSpec"]["inputSchema"]["json"]["properties"][prop] = {
                        "type": details.get("type", "string"),
                        "description": details.get("description", ""),
                    }

                new_tools.append(new_tool)

        return new_tools

    def generate_response(
        self,
        messages: List[Dict[str, str]],
        response_format=None,
        tools: Optional[List[Dict]] = None,
        tool_choice: str = "auto",
    ):
        """
        Generate a response based on the given messages using AWS Bedrock.

        Args:
            messages (list): List of message dicts containing 'role' and 'content'.
            tools (list, optional): List of tools that the model can call. Defaults to None.
            tool_choice (str, optional): Tool choice method. Defaults to "auto".

        Returns:
            str: The generated response.
        """

        if tools:
            # Use converse method when tools are provided
            messages = [
                {
                    "role": "user",
                    "content": [{"text": message["content"]} for message in messages],
                }
            ]
            inference_config = {
                "temperature": self.model_kwargs["temperature"],
                "maxTokens": self.model_kwargs["max_tokens_to_sample"],
                "topP": self.model_kwargs["top_p"],
            }
            tools_config = {"tools": self._convert_tool_format(tools)}

            response = self.client.converse(
                modelId=self.config.model,
                messages=messages,
                inferenceConfig=inference_config,
                toolConfig=tools_config,
            )
        else:
            # Use invoke_model method when no tools are provided
            prompt = self._format_messages(messages)
            provider = self.model.split(".")[0]
            input_body = self._prepare_input(provider, self.config.model, prompt, **self.model_kwargs)
            body = json.dumps(input_body)

            response = self.client.invoke_model(
                body=body,
                modelId=self.model,
                accept="application/json",
                contentType="application/json",
            )

        return self._parse_response(response, tools)
