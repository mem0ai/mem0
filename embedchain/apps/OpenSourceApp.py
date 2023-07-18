import logging
from typing import Iterable, Union

from embedchain.config import ChatConfig, OpenSourceAppConfig
from embedchain.embedchain import EmbedChain

gpt4all_model = None


class OpenSourceApp(EmbedChain):
    """
    The OpenSource app.
    Same as App, but uses an open source embedding model and LLM.

    Has two function: add and query.

    adds(data_type, url): adds the data from the given URL to the vector db.
    query(query): finds answer to the given query using vector database and LLM.
    """

    def __init__(self, config: OpenSourceAppConfig = None):
        """
        :param config: OpenSourceAppConfig instance to load as configuration. Optional.
        `ef` defaults to open source.
        """
        logging.info("Loading open source embedding model. This may take some time...")  # noqa:E501
        if not config:
            config = OpenSourceAppConfig()

        if not config.model:
            raise ValueError("OpenSourceApp needs a model to be instantiated. Maybe you passed the wrong config type?")

        self.instance = OpenSourceApp._get_instance(config.model)

        logging.info("Successfully loaded open source embedding model.")
        super().__init__(config)

    def get_llm_model_answer(self, prompt, config: ChatConfig):
        return self._get_gpt4all_answer(prompt=prompt, config=config)

    @staticmethod
    def _get_instance(model):
        try:
            from gpt4all import GPT4All
        except ModuleNotFoundError:
            raise ValueError(
                "The GPT4All python package is not installed. Please install it with `pip install GPT4All`"
            ) from None

        return GPT4All(model)

    def _get_gpt4all_answer(self, prompt: str, config: ChatConfig) -> Union[str, Iterable]:
        if config.model and config.model != self.config.model:
            raise RuntimeError(
                "OpenSourceApp does not support switching models at runtime. Please create a new app instance."
            )

        response = self.instance.generate(
            prompt=prompt,
            streaming=config.stream,
            top_p=config.top_p,
            max_tokens=config.max_tokens,
            temp=config.temperature,
        )
        return response
