import subprocess
import sys
import logging
from collections.abc import Iterable
from typing import Optional, Union

from langchain.callbacks.manager import CallbackManager
from langchain.callbacks.stdout import StdOutCallbackHandler
from langchain.callbacks.streaming_stdout import StreamingStdOutCallbackHandler
from langchain_community.llms.ollama import Ollama

try:
    from ollama import Client
except ImportError:
    user_input = input("The 'ollama' library is required. Install it now? [y/N]: ")
    if user_input.lower() == 'y':
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "ollama"])
            from ollama import Client
        except subprocess.CalledProcessError:
            print("Failed to install 'ollama'. Please install it manually using 'pip install ollama'.")
            sys.exit(1)
    else:
        raise ImportError("Ollama requires extra dependencies. Install with `pip install ollama`") from None

from embedchain.config import BaseLlmConfig
from embedchain.helpers.json_serializable import register_deserializable
from embedchain.llm.base import BaseLlm

logger = logging.getLogger(__name__)


@register_deserializable
class OllamaLlm(BaseLlm):
    def __init__(self, config: Optional[BaseLlmConfig] = None):
        super().__init__(config=config)
        if self.config.model is None:
            self.config.model = "llama2"

        client = Client(host=config.base_url)
        local_models = client.list()["models"]
        if not any(model.get("name") == self.config.model for model in local_models):
            logger.info(f"Pulling {self.config.model} from Ollama!")
            client.pull(self.config.model)

    def get_llm_model_answer(self, prompt):
        return self._get_answer(prompt=prompt, config=self.config)

    @staticmethod
    def _get_answer(prompt: str, config: BaseLlmConfig) -> Union[str, Iterable]:
        if config.stream:
            callbacks = config.callbacks if config.callbacks else [StreamingStdOutCallbackHandler()]
        else:
            callbacks = [StdOutCallbackHandler()]

        llm = Ollama(
            model=config.model,
            system=config.system_prompt,
            temperature=config.temperature,
            top_p=config.top_p,
            callback_manager=CallbackManager(callbacks),
            base_url=config.base_url,
        )

        return llm.invoke(prompt)
