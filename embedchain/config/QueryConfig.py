from embedchain.config.BaseConfig import BaseConfig
from string import Template
import re


DEFAULT_PROMPT_TEMPLATE = Template("""
  Use the following pieces of context to answer the query at the end.
  If you don't know the answer, just say that you don't know, don't try to make up an answer.

  $context
  
  Query: $query
  
  Helpful Answer:
""")
query_re = re.compile(r"\$\{*query\}*")
context_re = re.compile(r"\$\{*context\}*")


class QueryConfig(BaseConfig):
    """
    Config for the `query` method.
    """
    def __init__(self, template: Template = None):
        """
        Initializes the QueryConfig instance.

        :param template: Optional. The `Template` instance to use as a template for prompt.
        :raises ValueError: If the template is not valid as template should contain $context and $query
        """
        if template is None:
            template = DEFAULT_PROMPT_TEMPLATE
        if not (re.search(query_re, template.template) \
            and re.search(context_re, template.template)):
            raise ValueError("`template` should have `query` and `context` keys")
        self.template = template
