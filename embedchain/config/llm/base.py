import logging
import re
from string import Template
from typing import Any, Optional

from embedchain.config.base_config import BaseConfig
from embedchain.helpers.json_serializable import register_deserializable

DEFAULT_PROMPT = """
  Use the following pieces of context to answer the query at the end.
  If you don't know the answer, just say that you don't know, don't try to make up an answer.

  $context

  Query: $query

  Helpful Answer:
"""  # noqa:E501

DEFAULT_PROMPT_WITH_HISTORY = """
  Use the following pieces of context to answer the query at the end.
  If you don't know the answer, just say that you don't know, don't try to make up an answer.
  I will provide you with our conversation history.

  $context

  History: $history

  Query: $query

  Helpful Answer:
"""  # noqa:E501

DOCS_SITE_DEFAULT_PROMPT = """
  Use the following pieces of context to answer the query at the end.
  If you don't know the answer, just say that you don't know, don't try to make up an answer. Wherever possible, give complete code snippet. Dont make up any code snippet on your own.

  $context

  Query: $query

  Helpful Answer:
"""  # noqa:E501

DEFAULT_PROMPT_TEMPLATE = Template(DEFAULT_PROMPT)
DEFAULT_PROMPT_WITH_HISTORY_TEMPLATE = Template(DEFAULT_PROMPT_WITH_HISTORY)
DOCS_SITE_PROMPT_TEMPLATE = Template(DOCS_SITE_DEFAULT_PROMPT)
query_re = re.compile(r"\$\{*query\}*")
context_re = re.compile(r"\$\{*context\}*")
history_re = re.compile(r"\$\{*history\}*")


@register_deserializable
class BaseLlmConfig(BaseConfig):
    """
    Config for the `query` method.
    """

    def __init__(
        self,
        number_documents: int = 3,
        template: Optional[Template] = None,
        prompt: Optional[Template] = None,
        model: Optional[str] = None,
        temperature: float = 0,
        max_tokens: int = 1000,
        top_p: float = 1,
        stream: bool = False,
        deployment_name: Optional[str] = None,
        system_prompt: Optional[str] = None,
        where: dict[str, Any] = None,
        query_type: Optional[str] = None,
        callbacks: Optional[list] = None,
        api_key: Optional[str] = None,
        endpoint: Optional[str] = None,
        model_kwargs: Optional[dict[str, Any]] = None,
    ):
        """
        Initializes a configuration class instance for the LLM.

        Takes the place of the former `QueryConfig` or `ChatConfig`.

        :param number_documents:  Number of documents to pull from the database as
        context, defaults to 1
        :type number_documents: int, optional
        :param template:  The `Template` instance to use as a template for
        prompt, defaults to None (deprecated)
        :type template: Optional[Template], optional
        :param prompt: The `Template` instance to use as a template for
        prompt, defaults to None
        :type prompt: Optional[Template], optional
        :param model: Controls the OpenAI model used, defaults to None
        :type model: Optional[str], optional
        :param temperature:  Controls the randomness of the model's output.
        Higher values (closer to 1) make output more random, lower values make it more deterministic, defaults to 0
        :type temperature: float, optional
        :param max_tokens: Controls how many tokens are generated, defaults to 1000
        :type max_tokens: int, optional
        :param top_p: Controls the diversity of words. Higher values (closer to 1) make word selection more diverse,
        defaults to 1
        :type top_p: float, optional
        :param stream: Control if response is streamed back to user, defaults to False
        :type stream: bool, optional
        :param deployment_name: t.b.a., defaults to None
        :type deployment_name: Optional[str], optional
        :param system_prompt: System prompt string, defaults to None
        :type system_prompt: Optional[str], optional
        :param where: A dictionary of key-value pairs to filter the database results., defaults to None
        :type where: dict[str, Any], optional
        :param api_key: The api key of the custom endpoint, defaults to None
        :type api_key: Optional[str], optional
        :param endpoint: The api url of the custom endpoint, defaults to None
        :type endpoint: Optional[str], optional
        :param model_kwargs: A dictionary of key-value pairs to pass to the model, defaults to None
        :type model_kwargs: Optional[Dict[str, Any]], optional
        :param callbacks: Langchain callback functions to use, defaults to None
        :type callbacks: Optional[list], optional
        :param query_type: The type of query to use, defaults to None
        :type query_type: Optional[str], optional
        :raises ValueError: If the template is not valid as template should
        contain $context and $query (and optionally $history)
        :raises ValueError: Stream is not boolean
        """
        if template is not None:
            logging.warning(
                "The `template` argument is deprecated and will be removed in a future version. "
                + "Please use `prompt` instead."
            )
            if prompt is None:
                prompt = template

        if prompt is None:
            prompt = DEFAULT_PROMPT_TEMPLATE

        self.number_documents = number_documents
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.model = model
        self.top_p = top_p
        self.deployment_name = deployment_name
        self.system_prompt = system_prompt
        self.query_type = query_type
        self.callbacks = callbacks
        self.api_key = api_key
        self.endpoint = endpoint
        self.model_kwargs = model_kwargs

        if isinstance(prompt, str):
            prompt = Template(prompt)

        if self.validate_prompt(prompt):
            self.prompt = prompt
        else:
            raise ValueError("The 'prompt' should have 'query' and 'context' keys and potentially 'history' (if used).")

        if not isinstance(stream, bool):
            raise ValueError("`stream` should be bool")
        self.stream = stream
        self.where = where

    @staticmethod
    def validate_prompt(prompt: Template) -> Optional[re.Match[str]]:
        """
        validate the prompt

        :param prompt: the prompt to validate
        :type prompt: Template
        :return: valid (true) or invalid (false)
        :rtype: Optional[re.Match[str]]
        """
        return re.search(query_re, prompt.template) and re.search(context_re, prompt.template)

    @staticmethod
    def _validate_prompt_history(prompt: Template) -> Optional[re.Match[str]]:
        """
        validate the prompt with history

        :param prompt: the prompt to validate
        :type prompt: Template
        :return: valid (true) or invalid (false)
        :rtype: Optional[re.Match[str]]
        """
        return re.search(history_re, prompt.template)
