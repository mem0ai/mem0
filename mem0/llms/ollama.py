import requests
import json
import re
from typing import Dict, List, Optional, Union

from mem0.configs.llms.base import BaseLlmConfig
from mem0.configs.llms.ollama import OllamaConfig
from mem0.llms.base import LLMBase


class OllamaLLM(LLMBase):
    """Ollama LLM using HTTP API with qwen3.5 support."""
    
    def __init__(self, config: Optional[Union[BaseLlmConfig, OllamaConfig, Dict]] = None):
        if config is None:
            config = OllamaConfig()
        elif isinstance(config, dict):
            config = OllamaConfig(**config)
        elif isinstance(config, BaseLlmConfig) and not isinstance(config, OllamaConfig):
            config = OllamaConfig(
                model=config.model,
                temperature=config.temperature,
                api_key=config.api_key,
                max_tokens=config.max_tokens,
                top_p=config.top_p,
                top_k=config.top_k,
                enable_vision=config.enable_vision,
                vision_details=config.vision_details,
                http_client_proxies=config.http_client,
            )
        
        super().__init__(config)
        
        if not self.config.model:
            self.config.model = "llama3.1:8b"
        
        self.base_url = (self.config.ollama_base_url or "http://localhost:11434").rstrip('/')

    def _clean_qwen_output(self, content: str) -> str:
        """Clean qwen3.5 Thinking... prefix from output."""
        # Remove "Thinking..." and similar prefixes
        patterns = [
            r'^Thinking\.\.\.\s*',
            r'^Process\s*:\s*\d+\.\s*\*\*Analyze the Input:\*\*.*?\n\s*\*\s*Input:.*?\n',
            r'^Process\s*:\s*\d+\.\s*\*\*[^*]+\*\*.*?\n',
        ]
        
        cleaned = content
        for pattern in patterns:
            cleaned = re.sub(pattern, '', cleaned, flags=re.MULTILINE | re.DOTALL)
        
        return cleaned.strip()

    def _parse_response(self, response, tools):
        """Process the response."""
        if isinstance(response, dict):
            content = response.get("message", {}).get("content", "")
        else:
            content = response.message.content
        
        # Clean qwen3.5 output
        content = self._clean_qwen_output(content)
        
        if tools:
            return {
                "content": content,
                "tool_calls": [],
            }
        return content

    def generate_response(
        self,
        messages: List[Dict[str, str]],
        response_format=None,
        tools: Optional[List[Dict]] = None,
        tool_choice: str = "auto",
        **kwargs,
    ):
        """Generate a response using Ollama HTTP API."""
        url = f"{self.base_url}/api/chat"
        
        params = {
            "model": self.config.model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": self.config.temperature or 0.1,
                "num_predict": self.config.max_tokens or 2000,
                "top_p": self.config.top_p or 0.9,
            }
        }
        
        # Handle JSON response format
        if response_format and response_format.get("type") == "json_object":
            params["format"] = "json"
            if messages and messages[-1]["role"] == "user":
                messages[-1]["content"] += "\n\nPlease respond with valid JSON only."
        
        try:
            resp = requests.post(url, json=params, timeout=300)
            resp.raise_for_status()
            response = resp.json()
            return self._parse_response(response, tools)
        except Exception as e:
            raise RuntimeError(f"Ollama API error: {e}")
