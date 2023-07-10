from embedchain.config.BaseConfig import BaseConfig
from string import Template
import re

DEFAULT_PROMPT = """
  Use the following pieces of context to answer the query at the end.
  If you don't know the answer, just say that you don't know, don't try to make up an answer.

  $context

  Query: $query

  Helpful Answer:
"""

DEFAULT_PROMPT_TEMPLATE = Template(DEFAULT_PROMPT)
query_re = re.compile(r"\$\{*query\}*")
context_re = re.compile(r"\$\{*context\}*")

class QueryConfig(BaseConfig):
    """
    Config for the `query` method.
    """
    def __init__(self, template: Template = None, model = None, temperature = None, max_tokens = None, top_p = None):
        """
        Initializes the QueryConfig instance.

        :param template: Optional. The `Template` instance to use as a template for prompt.
        :param model: Optional. Controls the OpenAI model used.
        :param temperature: Optional. Controls the randomness of the model's output. 
                            Higher values (closer to 1) make output more random, lower values make it more deterministic.
        :param max_tokens: Optional. Controls how many tokens are generated.
        :param top_p: Optional. Controls the diversity of words. Higher values (closer to 1) make word selection more diverse, lower values make words less diverse.
        :raises ValueError: If the template is not valid as template should contain $context and $query
        """
        if template is None:
            template = DEFAULT_PROMPT_TEMPLATE
        if not (re.search(query_re, template.template) \
            and re.search(context_re, template.template)):
            raise ValueError("`template` should have `query` and `context` keys")
        self.template = template
        if temperature == None:
          self.temperature = 0
        else:
          self.temperature = temperature
        if max_tokens == None:
          self.max_tokens = 0
        else:
          self.max_tokens = max_tokens
        if model == None:
          self.model = "gpt-3.5-turbo-0613"
        else:
          self.model = model
        if top_p == None:
          self.top_p = 1
        else:
          self.top_p = top_p
