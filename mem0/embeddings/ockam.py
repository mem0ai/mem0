from typing import Literal, Optional

from mem0.configs.embeddings.base import BaseEmbedderConfig
from mem0.embeddings.base import EmbeddingBase

try:
    import litellm
except ImportError:
    raise ImportError("The 'litellm' library is required. Please install it using 'pip install litellm'.")


class OckamEmbedding(EmbeddingBase):
    def __init__(self, config: Optional[BaseEmbedderConfig] = None):
        super().__init__(config)

        if not self.config.ockam_model:
            raise ValueError("'ockam_model' is required for 'OckamEmbedding'.")

    async def embed(self, text, memory_action: Optional[Literal["add", "search", "update"]] = None):
        """
        Get the embedding for the given text using Ollama.

        Args:
            text (str): The text to embed.
            memory_action (optional): The type of embedding to use. Must be one of "add", "search", or "update". Defaults to None.
        Returns:
            list: The embedding vector.
        """
        ockam_model = self.config.ockam_model
        router = ockam_model.router()
        kwargs = ockam_model.kwargs
        response = await router.aembedding(model=ockam_model.name, input=text, **kwargs)
        return response.data[0]["embedding"]
