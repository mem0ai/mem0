from string import Template

from embedchain.config.QueryConfig import QueryConfig

DEFAULT_PROMPT = """
  You are a chatbot having a conversation with a human. You are given chat
  history and context.
  You need to answer the query considering context, chat history and your knowledge base. If you don't know the answer or the answer is neither contained in the context nor in history, then simply say "I don't know".

  $context

  History: $history

  Query: $query

  Helpful Answer:
"""  # noqa:E501

DEFAULT_PROMPT_TEMPLATE = Template(DEFAULT_PROMPT)


class ChatConfig(QueryConfig):
    """
    Config for the `chat` method, inherits from `QueryConfig`.
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
        :raises ValueError: If the template is not valid as template should contain
        $context and $query and $history
        """
        if template is None:
            template = DEFAULT_PROMPT_TEMPLATE

        # History is set as 0 to ensure that there is always a history, that way,
        # there don't have to be two templates. Having two templates would make it
        # complicated because the history is not user controlled.
        super().__init__(
            number_documents=number_documents,
            template=template,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=top_p,
            history=[0],
            stream=stream,
        )

    def set_history(self, history):
        """
        Chat history is not user provided and not set at initialization time

        :param history: (string) history to set
        """
        self.history = history
        return
