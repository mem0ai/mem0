import os
import json
from typing import Dict, List, Optional

import boto3

from mem0.llms.base import LLMBase


class AWSBedrockLLM(LLMBase):
    def __init__(self, model="amazon.titan-text-express-v1"):
        self.client = boto3.client("bedrock-runtime", "us-west-2" or os.environ.get("AWS_REGION"))
        self.model = model
        self.temperature = 0.1
        self.max_tokens_to_sample = 300
        self.top_p = 0.9

    def _format_messages(self, messages: List[Dict[str, str]]) -> str:
        """
        Format the messages into the required prompt structure.
        """
        formatted_messages = []
        for message in messages:
            role = message['role'].capitalize()
            content = message['content']
            formatted_messages.append(f"\n\n{role}: {content}")
        
        return "".join(formatted_messages) + "\n\nAssistant:"
    
    def _parse_response(self, response) -> str:
        """
        Parse the response from the API and extract the generated text.
        """
        if isinstance(response, dict) and 'body' in response:
            # For invoke_model response
            response_body = json.loads(response['body'].read().decode())
            return response_body.get('completion', '')
        elif isinstance(response, dict) and 'content' in response:
            return response
        else:
            return str(response)

    def generate_response(
        self,
        messages: List[Dict[str, str]],
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

        prompt = self._format_messages(messages)

        if tools:
            # Use converse method when tools are provided
            inference_config = {"temperature": self.temperature}
            additional_model_fields = {"top_p": self.top_p}
            tools_config = {"toolChoice": tool_choice, "tools": tools}

            response = self.client.converse(
                modelId=self.model,
                messages=messages,
                inferenceConfig=inference_config,
                additionalModelRequestFields=additional_model_fields,
                toolConfig=tools_config
            )
        else:
            # Use invoke_model method when no tools are provided
            body = json.dumps({
                "prompt": prompt,
                "max_tokens_to_sample": self.max_tokens_to_sample,
                "temperature": self.temperature,
                "top_p": self.top_p,
            })

            response = self.client.invoke_model(
                body=body,
                modelId=self.model,
                accept='application/json',
                contentType='application/json'
            )

        return self._parse_response(response)
