from embedchain.config.BaseConfig import BaseConfig

class QueryConfig(BaseConfig):
    """
    Config for the `query` method.
    """
    def __init__(self, number_documents=None):
        if number_documents is None:
            self.number_documents = 1
        else:
            self.number_documents = number_documents

