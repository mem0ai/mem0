from embedchain.config.BaseConfig import BaseConfig

class QueryConfig(BaseConfig):
    """
    Config for the `query` method.
    """
    def __init__(self, number_documents=None):
        """
        :param number_documents: Number of documents to pull from the database as context.
        """
        if number_documents is None:
            self.number_documents = 1
        else:
            self.number_documents = number_documents

