import os
from typing import Literal, Optional

try:
    from twelvelabs import TwelveLabs
except ImportError:
    raise ImportError("The 'twelvelabs' library is required. Please install it using 'pip install twelvelabs'.")

from mem0.configs.embeddings.base import BaseEmbedderConfig
from mem0.embeddings.base import EmbeddingBase


class TwelveLabsEmbedding(EmbeddingBase):
    """Embeddings using TwelveLabs Marengo.

    Marengo embeds text, image, audio and video into a single 512-dimensional
    multimodal latent space, so text describing a video memory shares a space
    with embeddings generated directly from the video itself. This makes it a
    good fit for multimodal memory.

    To summarize a video into memory text before storing it, see
    :meth:`summarize_video`, which uses the Pegasus video-understanding model.
    """

    def __init__(self, config: Optional[BaseEmbedderConfig] = None):
        super().__init__(config)

        self.config.model = self.config.model or "marengo3.0"
        self.config.embedding_dims = self.config.embedding_dims or 512
        api_key = self.config.api_key or os.getenv("TWELVELABS_API_KEY")
        if not api_key:
            raise ValueError(
                "TwelveLabs API key is required. Set TWELVELABS_API_KEY or pass api_key in the config. "
                "You can get a free key at https://twelvelabs.io."
            )
        self.client = TwelveLabs(api_key=api_key)

    def embed(self, text, memory_action: Optional[Literal["add", "search", "update"]] = None):
        """
        Get the embedding for the given text using TwelveLabs Marengo.

        Args:
            text (str): The text to embed.
            memory_action (optional): The type of embedding to use. Must be one of "add", "search", or "update". Defaults to None.
        Returns:
            list: The 512-dimensional embedding vector.
        """
        response = self.client.embed.create(model_name=self.config.model, text=text)
        return response.text_embedding.segments[0].float_

    def summarize_video(
        self,
        video_url: str,
        prompt: str = "Summarize this video in a few sentences for use as a memory.",
        model_name: str = "pegasus1.5",
        max_tokens: int = 2048,
    ) -> str:
        """Summarize a video into memory text using the Pegasus model.

        The returned text can be passed to ``Memory.add`` so the video's content
        becomes a searchable memory. Embedding that memory with Marengo keeps it
        in the same multimodal latent space as the video.

        Args:
            video_url: A publicly accessible URL of the video to summarize.
            prompt: Instruction passed to Pegasus.
            model_name: Pegasus model to use.
            max_tokens: Maximum number of tokens to generate.

        Returns:
            The generated summary text.
        """
        from twelvelabs.types.video_context import VideoContext_Url

        response = self.client.analyze(
            model_name=model_name,
            video=VideoContext_Url(url=video_url),
            prompt=prompt,
            max_tokens=max_tokens,
        )
        return response.data
