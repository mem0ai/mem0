import os
from typing import Optional, cast

from chromadb.api.types import EmbeddingFunction, Documents, Embeddings

from embedchain.config import BaseEmbedderConfig
from embedchain.embedder.base import BaseEmbedder
from embedchain.models import VectorDimensions


class ZhipiAIEmbeddingFunction(EmbeddingFunction[Documents]):
    def __init__(
        self,
        api_key: str,
        model_name: str = "embedding-2",
    ):
        """
        Initialize the ZhipiAIEmbeddingFunction.
        Args:
            api_key (str,): Your API key for the ZhipuAI API. If not
                provided, it will raise an error to provide an ZhipuAI API key.

            model_name (str, optional): The name of the model to use for text
                embeddings. Defaults to "embedding-2".

        """
        try:
            from zhipuai import ZhipuAI
        except ImportError:
            raise ValueError(
                "The zhipuai python package is not installed. Please install it with `pip install zhipuai`"
            )

        # If the api key is still not set, raise an error
        if api_key is None:
            raise ValueError(
                "Please provide an ZhipuAI API key. You can get one at https://open.bigmodel.cn/"
            )

        self._client=ZhipuAI(api_key=api_key)
        self._model_name = model_name

    def __call__(self, input: Documents) -> Embeddings:
        embeddings=[]
        for doc in input:
            embedding = self._client.embeddings.create(
                input=doc, model=self._model_name
            ).data[0].embedding
            embeddings.append(embedding)

        return cast(Embeddings, embeddings)


class ZhipuAIEmbedder(BaseEmbedder):
    def __init__(self, config: Optional[BaseEmbedderConfig] = None):
        super().__init__(config=config)

        if self.config.model is None:
            self.config.model = "embedding-2"

        api_key = self.config.api_key or os.environ["ZHIPU_API_KEY"]


        if api_key is None:
            raise ValueError(
                "ZHIPU_API_KEY  environment variables not provided"
            )  # noqa:E501
        embedding_fn = ZhipiAIEmbeddingFunction(
            api_key=api_key,
            model_name=self.config.model,
        )
        self.set_embedding_fn(embedding_fn=embedding_fn)
        vector_dimension = self.config.vector_dimension or VectorDimensions.ZHIPI_AI.value
        self.set_vector_dimension(vector_dimension=vector_dimension)
