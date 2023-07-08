from embedchain.config.BaseConfig import BaseConfig

class InitConfig(BaseConfig):
    """
    Config to initialize an embedchain `App` instance.
    """
    def __init__(self, ef=None, db=None):
        """
        :param ef: Optional. Embedding function to use.
        :param db: Optional. (Vector) database to use for embeddings.
        """
        # Embedding Function
        self.ef = ef
        self.db = db

        return


    def _set_embedding_function(self, ef):
        self.ef = ef
        return
    
    def _set_db(self, db):
        self.db = db
        return
