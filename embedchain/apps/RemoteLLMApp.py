import os

from embedchain.config import ChatConfig, RemoteLLMConfig
from embedchain.embedchain import EmbedChain


class RemoteLLMApp(EmbedChain):
    """The EmbedChain Remote LLM class.

    RemoteLLMApp allows you to use a self-hosted Remote LLM as a remote inference service.
    Used in production at Remote LLM to power Hugging Chat, the Inference API and Inference Endpoint.

    The users can self-host the Remote LLM as a remote inference service.
    """

    def __init__(self, config: RemoteLLMConfig):
        """
        :param config: AppConfig instance to load as configuration. Optional.
        """
        super().__init__(config)
        self.endpoint_url = getattr(config, "endpoint_url")
        self.response_key = getattr(config, "response_key", "generated_text")
        self.headers = {"Accept": "application/json"}
        authentication_token = getattr(config, "authentication_token", None)
        if authentication_token:
            self.headers.update({"authorization": "Bearer " + authentication_token})


    def get_llm_model_answer(self, prompt, chat_config: ChatConfig = None):
        if not chat_config:
            chat_config = ChatConfig(max_tokens=1024, temperature=0.1, top_p=0.95)
        if getattr(chat_config, "system_prompt"):
            raise ValueError("Remote LLM does not support `system_prompt`")
        
        import requests

        # One example is hugginface TGI, see the parameters
        # https://huggingface.github.io/text-generation-inference/#/Text%20Generation%20Inference/generate.
        parameters = {
            "best_of": 1,
            "max_new_tokens": chat_config.max_tokens,
            "temperature": chat_config.temperature,
            "top_p": chat_config.top_p,
        }

        request_input = {
            "inputs": prompt,
            "parameters": parameters,
        }

        response = requests.post(url=self.endpoint_url, json=request_input, headers=self.headers)
        if response.status_code == 200:
            result = response.json()
            if self.response_key in result:
                return result[self.response_key]
            else:
                raise ValueError(f"Error: no key {self.response_key} in response.")
        else:
            raise Exception(f"Error: {response.status_code}, {response.text}.")