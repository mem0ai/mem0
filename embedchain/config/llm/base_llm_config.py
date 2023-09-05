import re
from string import Template
from typing import Optional

from embedchain.config.BaseConfig import BaseConfig
from embedchain.helper_classes.json_serializable import register_deserializable

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
        number_documents=None,
        template: Template = None,
        model=None,
        temperature=None,
        max_tokens=None,
        top_p=None,
        stream: bool = False,
        deployment_name=None,
        system_prompt: Optional[str] = None,
        where=None,
    ):
        """
        Initializes the QueryConfig instance.

        :param number_documents: Number of documents to pull from the database as
        context.
        :param template: Optional. The `Template` instance to use as a template for
        prompt.
        :param model: Optional. Controls the OpenAI model used.
        :param temperature: Optional. Controls the randomness of the model's output.
        Higher values (closer to 1) make output more random, lower values make it more
        deterministic.
        :param max_tokens: Optional. Controls how many tokens are generated.
        :param top_p: Optional. Controls the diversity of words. Higher values
        (closer to 1) make word selection more diverse, lower values make words less
        diverse.
        :param stream: Optional. Control if response is streamed back to user
        :param deployment_name: t.b.a.
        :param system_prompt: Optional. System prompt string.
        :param where: Optional. A dictionary of key-value pairs to filter the database results.
        :raises ValueError: If the template is not valid as template should
        contain $context and $query (and optionally $history).
        """
        if number_documents is None:
            self.number_documents = 1
        else:
            self.number_documents = number_documents

        if template is None:
            template = DEFAULT_PROMPT_TEMPLATE

        self.temperature = temperature if temperature else 0
        self.max_tokens = max_tokens if max_tokens else 1000
        self.model = model
        self.top_p = top_p if top_p else 1
        self.deployment_name = deployment_name
        self.system_prompt = system_prompt

        if self.validate_template(template):
            self.template = template
        else:
            raise ValueError("`template` should have `query` and `context` keys and potentially `history` (if used).")

        if not isinstance(stream, bool):
            raise ValueError("`stream` should be bool")
        self.stream = stream
        self.where = where

    def validate_template(self, template: Template):
        """
        validate the template

        :param template: the template to validate
        :return: Boolean, valid (true) or invalid (false)
        """
        return re.search(query_re, template.template) and re.search(context_re, template.template)

    def _validate_template_history(self, template: Template):
        """
        validate the history template for history

        :param template: the template to validate
        :return: Boolean, valid (true) or invalid (false)
        """
        return re.search(history_re, template.template)
