import logging
from typing import Optional

from embedchain.apps.app import App
from embedchain.config import CustomAppConfig
from embedchain.helper.json_serializable import register_deserializable
from embedchain.llm.llama2 import Llama2Llm


@register_deserializable
class Llama2App(App):
    """
    The EmbedChain Llama2App class.

    Methods:
    add(source, data_type): adds the data from the given URL to the vector db.
    query(query): finds answer to the given query using vector database and LLM.
    chat(query): finds answer to the given query using vector database and LLM, with conversation history.

    .. deprecated:: 0.0.64
    Use `App` instead.
    """

    def __init__(self, config: CustomAppConfig = None, system_prompt: Optional[str] = None):
        """
        .. deprecated:: 0.0.64
        Use `App` instead.

        :param config: CustomAppConfig instance to load as configuration. Optional.
        :param system_prompt: System prompt string. Optional.
        """
        logging.warning(
            "DEPRECATION WARNING: Please use `App` instead of `Llama2App`. "
            "`Llama2App` will be removed in a future release. "
            "Please refer to https://docs.embedchain.ai/advanced/app_types#llama2app for instructions."
        )

        super().__init__(config=config, llm=Llama2Llm(), system_prompt=system_prompt)
