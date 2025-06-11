import os
from typing import Optional, Union

from chromadb import EmbeddingFunction, Embeddings

from embedchain.config import BaseEmbedderConfig
from embedchain.embedder.base import BaseEmbedder


class ClarifaiEmbeddingFunction(EmbeddingFunction):
    def __init__(self, config: BaseEmbedderConfig) -> None:
        super().__init__()
        try:
            from clarifai.client.input import Inputs
            from clarifai.client.model import Model
        except ModuleNotFoundError:
            raise ModuleNotFoundError(
                "The required dependencies for ClarifaiEmbeddingFunction are not installed."
                'Please install with `pip install --upgrade "embedchain[clarifai]"`'
            ) from None
        self.config = config
        self.api_key = config.api_key or os.getenv("CLARIFAI_PAT")
        self.model = config.model
        self.model_obj = Model(url=self.model, pat=self.api_key)
        self.input_obj = Inputs(pat=self.api_key)

    def __call__(self, input: Union[str, list[str]]) -> Embeddings:
        if isinstance(input, str):
            input = [input]

        batch_size = 32
        embeddings = []
        try:
            for i in range(0, len(input), batch_size):
                batch = input[i : i + batch_size]
                input_batch = [
                    self.input_obj.get_text_input(input_id=str(id), raw_text=inp) for id, inp in enumerate(batch)
                ]
                response = self.model_obj.predict(input_batch)
                embeddings.extend([list(output.data.embeddings[0].vector) for output in response.outputs])
        except Exception as e:
            print(f"Predict failed, exception: {e}")

        return embeddings


class ClarifaiEmbedder(BaseEmbedder):
    def __init__(self, config: Optional[BaseEmbedderConfig] = None):
        super().__init__(config)

        embedding_func = ClarifaiEmbeddingFunction(config=self.config)
        self.set_embedding_fn(embedding_fn=embedding_func)
