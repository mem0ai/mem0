from embedchain.config.QueryConfig import QueryConfig
from string import Template
class ChatConfig(QueryConfig):
    """
    Config for the `chat` method, inherits from `QueryConfig`.
    """
    def __init__(self, stream: bool = False, model = None, temperature = None, max_tokens = None, top_p = None):
        """
        Initializes the ChatConfig instance.
        :param template: Optional. The `Template` instance to use as a template for prompt.
        :param model: Optional. Controls the OpenAI model used.
        :param temperature: Optional. Controls the randomness of the model's output. 
                            Higher values (closer to 1) make output more random, lower values make it more deterministic.
        :param max_tokens: Optional. Controls how many tokens are generated.
        :param top_p: Optional. Controls the diversity of words. Higher values (closer to 1) make word selection more diverse, lower values make words less diverse.
        :raises ValueError: If the template is not valid as template should contain $context and $query
        """
        super().__init__(stream=stream, model=model, temperature=temperature, max_tokens=max_tokens, top_p=top_p)
