import os

from chromadb.utils import embedding_functions

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
    
    def _set_embedding_function_to_default(self):
        """
        Sets embedding function to default (`text-embedding-ada-002`).

        :raises ValueError: If the template is not valid as template should contain $context and $query
        """
        if os.getenv("OPENAI_API_KEY") is None or os.getenv("OPENAI_ORGANIZATION") is None:
            raise ValueError("OPENAI_API_KEY or OPENAI_ORGANIZATION environment variables not provided")
        self.ef = embedding_functions.OpenAIEmbeddingFunction(
                api_key=os.getenv("OPENAI_API_KEY"),
                organization_id=os.getenv("OPENAI_ORGANIZATION"),
                model_name="text-embedding-ada-002"
            )
    
    def _set_db(self, db):
        if db:
            self.db = db            
        return

    def _set_db_to_default(self):
        """
        Sets database to default (`ChromaDb`).
        """
        from embedchain.vectordb.chroma_db import ChromaDB
        self.db = ChromaDB(ef=self.ef)