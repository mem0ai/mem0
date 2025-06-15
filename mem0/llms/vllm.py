from typing import Dict, List, Optional

try:
    from vllm import LLM, SamplingParams
except ImportError:
    raise ImportError("The 'vllm' library is required. Please install it using 'pip install vllm'.")

from mem0.configs.llms.base import BaseLlmConfig
from mem0.llms.base import LLMBase


class VLLM(LLMBase):
    def __init__(self, config: Optional[BaseLlmConfig] = None):
        super().__init__(config)

        if not self.config.model:
            self.config.model = "HuggingFaceH4/zephyr-7b-beta" # Default vLLM model

        # Initialize vLLM client
        self.client = LLM(model=self.config.model, trust_remote_code=True)
        self.tokenizer = self.client.get_tokenizer()

    def _parse_response(self, response, tools):
        """
        Process the response based on whether tools are used or not.

        Args:
            response: The raw response from API.
            tools: The list of tools provided in the request.

        Returns:
            str or dict: The processed response.
        """
        # TODO: Implement tool calling for vLLM if supported and needed
        return response[0].outputs[0].text

    def generate_response(
        self,
        messages: List[Dict[str, str]],
        response_format=None,
        tools: Optional[List[Dict]] = None,
        tool_choice: str = "auto",
    ):
        """
        Generate a response based on the given messages using vLLM.

        Args:
            messages (list): List of message dicts containing 'role' and 'content'.
            response_format (str or object, optional): Format of the response. Defaults to "text".
            tools (list, optional): List of tools that the model can call. Defaults to None.
            tool_choice (str, optional): Tool choice method. Defaults to "auto".

        Returns:
            str: The generated response.
        """
        # Convert messages to a single prompt string
        prompt = self.tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)

        # Set sampling parameters
        sampling_params = SamplingParams(
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
            top_p=self.config.top_p,
        )

        # Generate response
        response = self.client.generate(prompt, sampling_params)

        return self._parse_response(response, tools) 