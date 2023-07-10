from embedchain.config.QueryConfig import QueryConfig

class ChatConfig(QueryConfig):
    """
    Config for the `chat` method, inherits from `QueryConfig`.
    """
    def __init__(self, stream: bool = False):
        """
        Initializes the QueryConfig instance.

        :param stream: Optional. Control if response is streamed back to the user
        :raises ValueError: If the template is not valid as template should contain $context and $query
        """
        super().__init__(stream=stream)