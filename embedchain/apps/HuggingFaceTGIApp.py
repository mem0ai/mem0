import os

from embedchain.config import ChatConfig, HuggingFaceTGIConfig
from embedchain.embedchain import EmbedChain


class HuggingFaceTGIApp(EmbedChain):
    """The EmbedChain HuggingFace TGI class.

    HuggingFace TGI is a Rust, Python and gRPC server for text generation inference.
    Used in production at HuggingFace to power Hugging Chat, the Inference API and Inference Endpoint.

    The users can self-host the HuggingFace TGI as a remote inference service.
    """

    def __init__(self, config: HuggingFaceTGIConfig = None):
        """
        :param config: AppConfig instance to load as configuration. Optional.
        """
        if "HTTP_ENDPOINT" not in os.environ:
            raise ValueError("Please set the HTTP_ENDPOINT in environment variable.")

        if config is None:
            config = HuggingFaceTGIConfig()

        super().__init__(config)

        self.headers = {"Accept": "application/json"}
        if config.authentication_token:
            self.headers.update({"authorization": "Bearer " + config.authentication_token})


    def get_llm_model_answer(self, prompt, config: ChatConfig = None):
        if config.system_prompt:
            raise ValueError("HuggingFaceTGI does not support `system_prompt`")
        
        # Set the default configure for the tgi request.
        max_new_tokens = 1024 if not config.max_tokens else config.max_tokens
        temperature = 0.1 if not config.temperature else config.temperature
        top_p = 0.95 if not config.top_p else config.top_p

        import requests

        # See https://huggingface.github.io/text-generation-inference/#/Text%20Generation%20Inference/generate.
        parameters = {
            "best_of": 1,
            "max_new_tokens": max_new_tokens,
            "temperature": temperature,
            "top_p": top_p,
            "repetition_penalty": 1.03,
        }

        request_input = {
            "inputs": prompt,
            "parameters": parameters,
        }

        response = requests.post(url=config.http_endpoint, json=request_input, headers=self.headers)
        if response.status_code == 200:
            result = response.json()
            return result["generated_text"]
        else:
            raise Exception(f"Error: {response.status_code}, {response.text}")