from typing import Callable, Optional

from embedchain.config.base_config import BaseConfig
from embedchain.helper.json_serializable import register_deserializable


@register_deserializable
class ChunkerConfig(BaseConfig):
    """
    Config for the chunker used in `add` method
    """

    def __init__(
        self,
        chunk_size: Optional[int] = None,
        chunk_overlap: Optional[int] = None,
        length_function: Optional[Callable[[str], int]] = None,
    ):
        self.chunk_size = chunk_size if chunk_size else 2000
        self.chunk_overlap = chunk_overlap if chunk_overlap else 0
        self.length_function = length_function if length_function else len


@register_deserializable
class LoaderConfig(BaseConfig):
    """
    Config for the chunker used in `add` method
    """

    def __init__(self):
        pass


@register_deserializable
class AddConfig(BaseConfig):
    """
    Config for the `add` method.
    """

    def __init__(
        self,
        chunker: Optional[ChunkerConfig] = None,
        loader: Optional[LoaderConfig] = None,
    ):
        """
        Initializes a configuration class instance for the `add` method.

        :param chunker: Chunker config, defaults to None
        :type chunker: Optional[ChunkerConfig], optional
        :param loader: Loader config, defaults to None
        :type loader: Optional[LoaderConfig], optional
        """
        self.loader = loader
        self.chunker = chunker
