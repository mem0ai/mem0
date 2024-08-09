from typing import Optional, Dict, List, Union, Mapping
import json
import httpx

from mem0.llms.base import LLMBase
from mem0.configs.llms.base import BaseLlmConfig

try:
    from portkey_ai import Portkey
except ImportError:
    raise ImportError(
        "Portkey requires extra dependencies. Install with `pip install portkey-ai`"
    ) from None


class PortkeyConfig(BaseLlmConfig):
    def __init__(
        self,
        model: Optional[str] = None,
        temperature: float = 0,
        max_tokens: int = 3000,
        top_p: float = 1,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        virtual_key: Optional[str] = None,
        config: Optional[Union[Mapping, str]] = None,
        provider: Optional[str] = None,
        trace_id: Optional[str] = None,
        metadata: Union[Optional[dict[str, str]], str] = None,
        cache_namespace: Optional[str] = None,
        debug: Optional[bool] = None,
        cache_force_refresh: Optional[bool] = None,
        custom_host: Optional[str] = None,
        forward_headers: Optional[List[str]] = None,
        openai_project: Optional[str] = None,
        openai_organization: Optional[str] = None,
        aws_secret_access_key: Optional[str] = None,
        aws_access_key_id: Optional[str] = None,
        aws_session_token: Optional[str] = None,
        aws_region: Optional[str] = None,
        vertex_project_id: Optional[str] = None,
        vertex_region: Optional[str] = None,
        workers_ai_account_id: Optional[str] = None,
        azure_resource_name: Optional[str] = None,
        azure_deployment_id: Optional[str] = None,
        azure_api_version: Optional[str] = None,
        http_client: Optional[httpx.Client] = None,
        request_timeout: Optional[int] = None,
        Authorization: Optional[str] = None,
    ):

        super().__init__(model, temperature, max_tokens, top_p)

        self.provider = provider
        self.api_key = api_key
        self.base_url = base_url
        self.virtual_key = virtual_key
        self.config = config
        self.trace_id = trace_id
        self.metadata = metadata
        self.cache_namespace = cache_namespace
        self.debug = debug
        self.cache_force_refresh = cache_force_refresh
        self.custom_host = custom_host
        self.forward_headers = forward_headers
        self.openai_project = openai_project
        self.openai_organization = openai_organization
        self.aws_secret_access_key = aws_secret_access_key
        self.aws_access_key_id = aws_access_key_id
        self.aws_session_token = aws_session_token
        self.aws_region = aws_region
        self.vertex_project_id = vertex_project_id
        self.vertex_region = vertex_region
        self.workers_ai_account_id = workers_ai_account_id
        self.azure_resource_name = azure_resource_name
        self.azure_deployment_id = azure_deployment_id
        self.azure_api_version = azure_api_version
        self.http_client = http_client
        self.request_timeout = request_timeout
        self.Authorization = Authorization


class PortkeyLLM(LLMBase):
    def __init__(self, configDict: Optional[Dict]):
        self.config = PortkeyConfig(**configDict)
        self.client = Portkey(**configDict)

    def _parse_response(self, response, tools):
        """
        Process the response based on whether tools are used or not.

        Args:
            response: The raw response from API.
            tools: The list of tools provided in the request.

        Returns:
            str or dict: The processed response.
        """
        if tools:
            processed_response = {
                "content": response.choices[0].message.content,
                "tool_calls": [],
            }

            if response.choices[0].message.tool_calls:
                for tool_call in response.choices[0].message.tool_calls:
                    processed_response["tool_calls"].append(
                        {
                            "name": tool_call.function.name,
                            "arguments": json.loads(tool_call.function.arguments),
                        }
                    )

            return processed_response
        else:
            return response.choices[0].message.content

    def generate_response(
        self,
        messages: List[Dict[str, str]],
        response_format=None,
        tools: Optional[List[Dict]] = None,
        tool_choice: str = "auto",
    ):
        """
        Generate a response based on the given messages using Portkey.

        Args:
            messages (list): List of message dicts containing 'role' and 'content'.
            response_format (str or object, optional): Format of the response. Defaults to "text".
            tools (list, optional): List of tools that the model can call. Defaults to None.
            tool_choice (str, optional): Tool choice method. Defaults to "auto".

        Returns:
            str: The generated response.
        """
        params = {
            "messages": messages,
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
            "top_p": self.config.top_p,
        }
        if response_format:
            params["response_format"] = response_format
        if tools:
            params["tools"] = tools
            params["tool_choice"] = tool_choice
        if self.config.model:
            params["model"] = self.config.model

        response = self.client.chat.completions.create(**params)
        return self._parse_response(response, tools)
