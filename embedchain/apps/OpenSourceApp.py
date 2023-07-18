import logging

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

        logging.info("Successfully loaded open source embedding model.")
        super().__init__(config)

    def get_llm_model_answer(self, prompt, config: ChatConfig):
        from gpt4all import GPT4All

        global gpt4all_model
        if gpt4all_model is None:
            gpt4all_model = GPT4All("orca-mini-3b.ggmlv3.q4_0.bin")
        response = gpt4all_model.generate(prompt=prompt, streaming=config.stream)
        return response
