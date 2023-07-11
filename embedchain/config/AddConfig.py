from typing import Callable, Optional

from embedchain.config.BaseConfig import BaseConfig


class ChunkerConfig(BaseConfig):
    """
    Config for the chunker used in `add` method
    """

    def __init__(
        self,
        chunk_size: Optional[int] = 4000,
        chunk_overlap: Optional[int] = 200,
        length_function: Optional[Callable[[str], int]] = len,
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.length_function = length_function


class LoaderConfig(BaseConfig):
    """
    Config for the chunker used in `add` method
    """

    def __init__(self):
        pass


class AddConfig(BaseConfig):
    """
    Config for the `add` method.
    """

    def __init__(
        self,
        chunker: Optional[ChunkerConfig] = None,
        loader: Optional[LoaderConfig] = None,
    ):
        self.loader = loader
        self.chunker = chunker
