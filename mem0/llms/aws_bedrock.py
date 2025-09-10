import json
import logging
import re
from typing import Any, Dict, List, Optional, Union

try:
    import boto3
    from botocore.exceptions import ClientError, NoCredentialsError
except ImportError:
    raise ImportError("The 'boto3' library is required. Please install it using 'pip install boto3'.")

from mem0.configs.llms.base import BaseLlmConfig
from mem0.configs.llms.aws_bedrock import AWSBedrockConfig
from mem0.llms.base import LLMBase

logger = logging.getLogger(__name__)

PROVIDERS = [
    "ai21", "amazon", "anthropic", "cohere", "meta", "mistral", "stability", "writer", 
    "deepseek", "gpt-oss", "perplexity", "snowflake", "titan", "command", "j2", "llama"
]


def extract_provider(model: str) -> str:
    """Extract provider from model identifier."""
    for provider in PROVIDERS:
        if re.search(rf"\b{re.escape(provider)}\b", model):
            return provider
    raise ValueError(f"Unknown provider in model: {model}")


class AWSBedrockLLM(LLMBase):
    """
    AWS Bedrock LLM integration for Mem0.

    Supports all available Bedrock models with automatic provider detection.
    """

    def __init__(self, config: Optional[Union[AWSBedrockConfig, BaseLlmConfig, Dict]] = None):
        """
        Initialize AWS Bedrock LLM.

        Args:
            config: AWS Bedrock configuration object
        """
        # Convert to AWSBedrockConfig if needed
        if config is None:
            config = AWSBedrockConfig()
        elif isinstance(config, dict):
            config = AWSBedrockConfig(**config)
        elif isinstance(config, BaseLlmConfig) and not isinstance(config, AWSBedrockConfig):
            # Convert BaseLlmConfig to AWSBedrockConfig
            config = AWSBedrockConfig(
                model=config.model,
                temperature=config.temperature,
                max_tokens=config.max_tokens,
                top_p=config.top_p,
                top_k=config.top_k,
                enable_vision=getattr(config, "enable_vision", False),
            )

        super().__init__(config)
        self.config = config

        # Initialize AWS client
        self._initialize_aws_client()

        # Get model configuration
        self.model_config = self.config.get_model_config()
        self.provider = extract_provider(self.config.model)

        # Initialize provider-specific settings
        self._initialize_provider_settings()

    def _initialize_aws_client(self):
        """Initialize AWS Bedrock client with proper credentials."""
        try:
            aws_config = self.config.get_aws_config()

            # Create Bedrock runtime client
            self.client = boto3.client("bedrock-runtime", **aws_config)

            # Test connection
            self._test_connection()

        except NoCredentialsError:
            raise ValueError(
                "AWS credentials not found. Please set AWS_ACCESS_KEY_ID, "
                "AWS_SECRET_ACCESS_KEY, and AWS_REGION environment variables, "
                "or provide them in the config."
            )
        except ClientError as e:
            if e.response["Error"]["Code"] == "UnauthorizedOperation":
                raise ValueError(
                    f"Unauthorized access to Bedrock. Please ensure your AWS credentials "
                    f"have permission to access Bedrock in region {self.config.aws_region}."
                )
            else:
                raise ValueError(f"AWS Bedrock error: {e}")

    def _test_connection(self):
        """Test connection to AWS Bedrock service."""
        try:
            # List available models to test connection
            bedrock_client = boto3.client("bedrock", **self.config.get_aws_config())
            response = bedrock_client.list_foundation_models()
            self.available_models = [model["modelId"] for model in response["modelSummaries"]]

            # Check if our model is available
            if self.config.model not in self.available_models:
                logger.warning(f"Model {self.config.model} may not be available in region {self.config.aws_region}")
                logger.info(f"Available models: {', '.join(self.available_models[:5])}...")

        except Exception as e:
            logger.warning(f"Could not verify model availability: {e}")
            self.available_models = []

    def _initialize_provider_settings(self):
        """Initialize provider-specific settings and capabilities."""
        # Determine capabilities based on provider and model
        self.supports_tools = self.provider in ["anthropic", "cohere", "amazon"]
        self.supports_vision = self.provider in ["anthropic", "amazon", "meta", "mistral"]
        self.supports_streaming = self.provider in ["anthropic", "cohere", "mistral", "amazon", "meta"]

        # Set message formatting method
        if self.provider == "anthropic":
            self._format_messages = self._format_messages_anthropic
        elif self.provider == "cohere":
            self._format_messages = self._format_messages_cohere
        elif self.provider == "amazon":
            self._format_messages = self._format_messages_amazon
        elif self.provider == "meta":
            self._format_messages = self._format_messages_meta
        elif self.provider == "mistral":
            self._format_messages = self._format_messages_mistral
        else:
            self._format_messages = self._format_messages_generic

    def _format_messages_anthropic(self, messages: List[Dict[str, str]]) -> tuple[List[Dict[str, Any]], Optional[str]]:
        """Format messages for Anthropic models."""
        formatted_messages = []
        system_message = None

        for message in messages:
            role = message["role"]
            content = message["content"]

            if role == "system":
                # Anthropic supports system messages as a separate parameter
                # see: https://docs.anthropic.com/en/docs/build-with-claude/prompt-engineering/system-prompts
                system_message = content
            elif role == "user":
                # Use Converse API format
                formatted_messages.append({"role": "user", "content": [{"text": content}]})
            elif role == "assistant":
                # Use Converse API format
                formatted_messages.append({"role": "assistant", "content": [{"text": content}]})

        return formatted_messages, system_message

    def _format_messages_cohere(self, messages: List[Dict[str, str]]) -> str:
        """Format messages for Cohere models."""
        formatted_messages = []

        for message in messages:
            role = message["role"].capitalize()
            content = message["content"]
            formatted_messages.append(f"{role}: {content}")

        return "\n".join(formatted_messages)

    def _format_messages_amazon(self, messages: List[Dict[str, str]]) -> List[Dict[str, Any]]:
        """Format messages for Amazon models (including Nova)."""
        formatted_messages = []
        
        for message in messages:
            role = message["role"]
            content = message["content"]
            
            if role == "system":
                # Amazon models support system messages
                formatted_messages.append({"role": "system", "content": content})
            elif role == "user":
                formatted_messages.append({"role": "user", "content": content})
            elif role == "assistant":
                formatted_messages.append({"role": "assistant", "content": content})
        
        return formatted_messages

    def _format_messages_meta(self, messages: List[Dict[str, str]]) -> str:
        """Format messages for Meta models."""
        formatted_messages = []
        
        for message in messages:
            role = message["role"].capitalize()
            content = message["content"]
            formatted_messages.append(f"{role}: {content}")
        
        return "\n".join(formatted_messages)

    def _format_messages_mistral(self, messages: List[Dict[str, str]]) -> List[Dict[str, Any]]:
        """Format messages for Mistral models."""
        formatted_messages = []
        
        for message in messages:
            role = message["role"]
            content = message["content"]
            
            if role == "system":
                # Mistral supports system messages
                formatted_messages.append({"role": "system", "content": content})
            elif role == "user":
                formatted_messages.append({"role": "user", "content": content})
            elif role == "assistant":
                formatted_messages.append({"role": "assistant", "content": content})
        
        return formatted_messages

    def _format_messages_generic(self, messages: List[Dict[str, str]]) -> str:
        """Generic message formatting for other providers."""
        formatted_messages = []

        for message in messages:
            role = message["role"].capitalize()
            content = message["content"]
            formatted_messages.append(f"\n\n{role}: {content}")

        return "\n\nHuman: " + "".join(formatted_messages) + "\n\nAssistant:"

    def _prepare_input(self, prompt: str) -> Dict[str, Any]:
        """
        Prepare input for the current provider's model.

        Args:
            prompt: Text prompt to process

        Returns:
            Prepared input dictionary
        """
        # Base configuration
        input_body = {"prompt": prompt}

        # Provider-specific parameter mappings
        provider_mappings = {
            "meta": {"max_tokens": "max_gen_len"},
            "ai21": {"max_tokens": "maxTokens", "top_p": "topP"},
            "mistral": {"max_tokens": "max_tokens"},
            "cohere": {"max_tokens": "max_tokens", "top_p": "p"},
            "amazon": {"max_tokens": "maxTokenCount", "top_p": "topP"},
            "anthropic": {"max_tokens": "max_tokens", "top_p": "top_p"},
        }

        # Apply provider mappings
        if self.provider in provider_mappings:
            for old_key, new_key in provider_mappings[self.provider].items():
                if old_key in self.model_config:
                    input_body[new_key] = self.model_config[old_key]

        # Special handling for specific providers
        if self.provider == "cohere" and "cohere.command" in self.config.model:
            input_body["message"] = input_body.pop("prompt")
        elif self.provider == "amazon":
            # Amazon Nova and other Amazon models
            if "nova" in self.config.model.lower():
                # Nova models use the converse API format
                input_body = {
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": self.model_config.get("max_tokens", 5000),
                    "temperature": self.model_config.get("temperature", 0.1),
                    "top_p": self.model_config.get("top_p", 0.9),
                }
            else:
                # Legacy Amazon models
                input_body = {
                    "inputText": prompt,
                    "textGenerationConfig": {
                        "maxTokenCount": self.model_config.get("max_tokens", 5000),
                        "topP": self.model_config.get("top_p", 0.9),
                        "temperature": self.model_config.get("temperature", 0.1),
                    },
                }
                # Remove None values
                input_body["textGenerationConfig"] = {
                    k: v for k, v in input_body["textGenerationConfig"].items() if v is not None
                }
        elif self.provider == "anthropic":
            input_body = {
                "messages": [{"role": "user", "content": [{"type": "text", "text": prompt}]}],
                "max_tokens": self.model_config.get("max_tokens", 2000),
                "temperature": self.model_config.get("temperature", 0.1),
                "top_p": self.model_config.get("top_p", 0.9),
                "anthropic_version": "bedrock-2023-05-31",
            }
        elif self.provider == "meta":
            input_body = {
                "prompt": prompt,
                "max_gen_len": self.model_config.get("max_tokens", 5000),
                "temperature": self.model_config.get("temperature", 0.1),
                "top_p": self.model_config.get("top_p", 0.9),
            }
        elif self.provider == "mistral":
            input_body = {
                "prompt": prompt,
                "max_tokens": self.model_config.get("max_tokens", 5000),
                "temperature": self.model_config.get("temperature", 0.1),
                "top_p": self.model_config.get("top_p", 0.9),
            }
        else:
            # Generic case - add all model config parameters
            input_body.update(self.model_config)

        return input_body

    def _convert_tool_format(self, original_tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Convert tools to Bedrock-compatible format.

        Args:
            original_tools: List of tool definitions

        Returns:
            Converted tools in Bedrock format
        """
        new_tools = []

        for tool in original_tools:
            if tool["type"] == "function":
                function = tool["function"]
                new_tool = {
                    "toolSpec": {
                        "name": function["name"],
                        "description": function.get("description", ""),
                        "inputSchema": {
                            "json": {
                                "type": "object",
                                "properties": {},
                                "required": function["parameters"].get("required", []),
                            }
                        },
                    }
                }

                # Add properties
                for prop, details in function["parameters"].get("properties", {}).items():
                    new_tool["toolSpec"]["inputSchema"]["json"]["properties"][prop] = details

                new_tools.append(new_tool)

        return new_tools

    def _parse_response(
        self, response: Dict[str, Any], tools: Optional[List[Dict]] = None
    ) -> Union[str, Dict[str, Any]]:
        """
        Parse response from Bedrock API.

        Args:
            response: Raw API response
            tools: List of tools if used

        Returns:
            Parsed response
        """
        if tools:
            # Handle tool-enabled responses
            processed_response = {"tool_calls": []}

            if response.get("output", {}).get("message", {}).get("content"):
                for item in response["output"]["message"]["content"]:
                    if "toolUse" in item:
                        processed_response["tool_calls"].append(
                            {
                                "name": item["toolUse"]["name"],
                                "arguments": item["toolUse"]["input"],
                            }
                        )

            return processed_response

        # Handle regular text responses
        try:
            response_body = response.get("body").read().decode()
            response_json = json.loads(response_body)

            # Provider-specific response parsing
            if self.provider == "anthropic":
                return response_json.get("content", [{"text": ""}])[0].get("text", "")
            elif self.provider == "amazon":
                # Handle both Nova and legacy Amazon models
                if "nova" in self.config.model.lower():
                    # Nova models return content in a different format
                    if "content" in response_json:
                        return response_json["content"][0]["text"]
                    elif "completion" in response_json:
                        return response_json["completion"]
                else:
                    # Legacy Amazon models
                    return response_json.get("completion", "")
            elif self.provider == "meta":
                return response_json.get("generation", "")
            elif self.provider == "mistral":
                return response_json.get("outputs", [{"text": ""}])[0].get("text", "")
            elif self.provider == "cohere":
                return response_json.get("generations", [{"text": ""}])[0].get("text", "")
            elif self.provider == "ai21":
                return response_json.get("completions", [{"data", {"text": ""}}])[0].get("data", {}).get("text", "")
            else:
                # Generic parsing - try common response fields
                for field in ["content", "text", "completion", "generation"]:
                    if field in response_json:
                        if isinstance(response_json[field], list) and response_json[field]:
                            return response_json[field][0].get("text", "")
                        elif isinstance(response_json[field], str):
                            return response_json[field]

                # Fallback
                return str(response_json)

        except Exception as e:
            logger.warning(f"Could not parse response: {e}")
            return "Error parsing response"

    def generate_response(
        self,
        messages: List[Dict[str, str]],
        response_format: Optional[str] = None,
        tools: Optional[List[Dict]] = None,
        tool_choice: str = "auto",
        stream: bool = False,
        **kwargs,
    ) -> Union[str, Dict[str, Any]]:
        """
        Generate response using AWS Bedrock.

        Args:
            messages: List of message dictionaries
            response_format: Response format specification
            tools: List of tools for function calling
            tool_choice: Tool choice method
            stream: Whether to stream the response
            **kwargs: Additional parameters

        Returns:
            Generated response
        """
        try:
            if tools and self.supports_tools:
                # Use converse method for tool-enabled models
                return self._generate_with_tools(messages, tools, stream)
            else:
                # Use standard invoke_model method
                return self._generate_standard(messages, stream)

        except Exception as e:
            logger.error(f"Failed to generate response: {e}")
            raise RuntimeError(f"Failed to generate response: {e}")

    @staticmethod
    def _convert_tools_to_converse_format(tools: List[Dict]) -> List[Dict]:
        """Convert OpenAI-style tools to Converse API format."""
        if not tools:
            return []

        converse_tools = []
        for tool in tools:
            if tool.get("type") == "function" and "function" in tool:
                func = tool["function"]
                converse_tool = {
                    "toolSpec": {
                        "name": func["name"],
                        "description": func.get("description", ""),
                        "inputSchema": {
                            "json": func.get("parameters", {})
                        }
                    }
                }
                converse_tools.append(converse_tool)

        return converse_tools

    def _generate_with_tools(self, messages: List[Dict[str, str]], tools: List[Dict], stream: bool = False) -> Dict[str, Any]:
        """Generate response with tool calling support using correct message format."""
        # Format messages for tool-enabled models
        system_message = None
        if self.provider == "anthropic":
            formatted_messages, system_message = self._format_messages_anthropic(messages)
        elif self.provider == "amazon":
            formatted_messages = self._format_messages_amazon(messages)
        else:
            formatted_messages = [{"role": "user", "content": [{"text": messages[-1]["content"]}]}]

        # Prepare tool configuration in Converse API format
        tool_config = None
        if tools:
            converse_tools = self._convert_tools_to_converse_format(tools)
            if converse_tools:
                tool_config = {"tools": converse_tools}

        # Prepare converse parameters
        converse_params = {
            "modelId": self.config.model,
            "messages": formatted_messages,
            "inferenceConfig": {
                "maxTokens": self.model_config.get("max_tokens", 2000),
                "temperature": self.model_config.get("temperature", 0.1),
                "topP": self.model_config.get("top_p", 0.9),
            }
        }

        # Add system message if present (for Anthropic)
        if system_message:
            converse_params["system"] = [{"text": system_message}]

        # Add tool config if present
        if tool_config:
            converse_params["toolConfig"] = tool_config

        # Make API call
        response = self.client.converse(**converse_params)

        return self._parse_response(response, tools)

    def _generate_standard(self, messages: List[Dict[str, str]], stream: bool = False) -> str:
        """Generate standard text response using Converse API for Anthropic models."""
        # For Anthropic models, always use Converse API
        if self.provider == "anthropic":
            formatted_messages, system_message = self._format_messages_anthropic(messages)

            # Prepare converse parameters
            converse_params = {
                "modelId": self.config.model,
                "messages": formatted_messages,
                "inferenceConfig": {
                    "maxTokens": self.model_config.get("max_tokens", 2000),
                    "temperature": self.model_config.get("temperature", 0.1),
                    "topP": self.model_config.get("top_p", 0.9),
                }
            }

            # Add system message if present
            if system_message:
                converse_params["system"] = [{"text": system_message}]

            # Use converse API for Anthropic models
            response = self.client.converse(**converse_params)

            # Parse Converse API response
            if hasattr(response, 'output') and hasattr(response.output, 'message'):
                return response.output.message.content[0].text
            elif 'output' in response and 'message' in response['output']:
                return response['output']['message']['content'][0]['text']
            else:
                return str(response)

        elif self.provider == "amazon" and "nova" in self.config.model.lower():
            # Nova models use converse API even without tools
            formatted_messages = self._format_messages_amazon(messages)
            input_body = {
                "messages": formatted_messages,
                "max_tokens": self.model_config.get("max_tokens", 5000),
                "temperature": self.model_config.get("temperature", 0.1),
                "top_p": self.model_config.get("top_p", 0.9),
            }
            
            # Use converse API for Nova models
            response = self.client.converse(
                modelId=self.config.model,
                messages=input_body["messages"],
                inferenceConfig={
                    "maxTokens": input_body["max_tokens"],
                    "temperature": input_body["temperature"],
                    "topP": input_body["top_p"],
                }
            )
            
            return self._parse_response(response)
        else:
            prompt = self._format_messages(messages)
            input_body = self._prepare_input(prompt)

        # Convert to JSON
        body = json.dumps(input_body)

        # Make API call
        response = self.client.invoke_model(
            body=body,
            modelId=self.config.model,
            accept="application/json",
            contentType="application/json",
        )

        return self._parse_response(response)

    def list_available_models(self) -> List[Dict[str, Any]]:
        """List all available models in the current region."""
        try:
            bedrock_client = boto3.client("bedrock", **self.config.get_aws_config())
            response = bedrock_client.list_foundation_models()

            models = []
            for model in response["modelSummaries"]:
                provider = extract_provider(model["modelId"])
                models.append(
                    {
                        "model_id": model["modelId"],
                        "provider": provider,
                        "model_name": model["modelId"].split(".", 1)[1]
                        if "." in model["modelId"]
                        else model["modelId"],
                        "modelArn": model.get("modelArn", ""),
                        "providerName": model.get("providerName", ""),
                        "inputModalities": model.get("inputModalities", []),
                        "outputModalities": model.get("outputModalities", []),
                        "responseStreamingSupported": model.get("responseStreamingSupported", False),
                    }
                )

            return models

        except Exception as e:
            logger.warning(f"Could not list models: {e}")
            return []

    def get_model_capabilities(self) -> Dict[str, Any]:
        """Get capabilities of the current model."""
        return {
            "model_id": self.config.model,
            "provider": self.provider,
            "model_name": self.config.model_name,
            "supports_tools": self.supports_tools,
            "supports_vision": self.supports_vision,
            "supports_streaming": self.supports_streaming,
            "max_tokens": self.model_config.get("max_tokens", 2000),
        }

    def validate_model_access(self) -> bool:
        """Validate if the model is accessible."""
        try:
            # Try to invoke the model with a minimal request
            if self.provider == "amazon" and "nova" in self.config.model.lower():
                # Test Nova model with converse API
                test_messages = [{"role": "user", "content": "test"}]
                self.client.converse(
                    modelId=self.config.model,
                    messages=test_messages,
                    inferenceConfig={"maxTokens": 10}
                )
            else:
                # Test other models with invoke_model
                test_body = json.dumps({"prompt": "test"})
                self.client.invoke_model(
                    body=test_body,
                    modelId=self.config.model,
                    accept="application/json",
                    contentType="application/json",
                )
            return True
        except Exception:
            return False
