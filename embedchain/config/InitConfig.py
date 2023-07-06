import os

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
        if ef is None:
            from chromadb.utils import embedding_functions
            self.ef = embedding_functions.OpenAIEmbeddingFunction(
                api_key=os.getenv("OPENAI_API_KEY"),
                organization_id=os.getenv("OPENAI_ORGANIZATION"),
                model_name="text-embedding-ada-002"
            )
        else:
            self.ef = ef

        if db is None:
            from embedchain.vectordb.chroma_db import ChromaDB
            self.db = ChromaDB(ef=self.ef)
        else:
            self.db = db

        return


    def _set_embedding_function(self, ef):
        self.ef = ef
        return        
