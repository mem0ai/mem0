from string import Template
from typing import Optional
import logging

from embedchain.config.QueryConfig import QueryConfig


class ChatConfig(QueryConfig):
    """
    Config for the `chat` method, inherits from `QueryConfig`.

    DEPRECATED: Please use `QueryConfig` instead.
    """

    def __init__(
        self,
        number_documents=None,
        template: Template = None,
        model=None,
        temperature=None,
        max_tokens=None,
        top_p=None,
        stream: bool = False,
        deployment_name=None,
        system_prompt: Optional[str] = None,
    ):
        """
        Initializes the ChatConfig instance.

        :param number_documents: Number of documents to pull from the database as
        context.
        :param template: Optional. The `Template` instance to use as a template for
        prompt.
        :param model: Optional. Controls the OpenAI model used.
        :param temperature: Optional. Controls the randomness of the model's output.
        Higher values (closer to 1) make output more random,lower values make it more
        deterministic.
        :param max_tokens: Optional. Controls how many tokens are generated.
        :param top_p: Optional. Controls the diversity of words.Higher values
        (closer to 1) make word selection more diverse, lower values make words less
        diverse.
        :param stream: Optional. Control if response is streamed back to the user
        :param deployment_name: t.b.a.
        :param system_prompt: Optional. System prompt string.
        :raises ValueError: If the template is not valid as template should contain
        $context and $query and $history
        """
        logging.warning("DEPRECATION WARNING: `ChatConfig` is deprecated in favor of `QueryConfig`. It's not maintained and will be removed in a future update. Please use `QueryConfig` in the `chat` and `query` method.")

        super().__init__(
            number_documents=number_documents,
            template=template,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=top_p,
            history=[None],
            stream=stream,
            deployment_name=deployment_name,
            system_prompt=system_prompt,
        )
