from typing import Callable, Optional

from embedchain.config.BaseConfig import BaseConfig


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
        self.chunk_size = 2000 if chunk_size is None else chunk_size
        self.chunk_overlap = 0 if chunk_overlap is None else chunk_overlap
        self.length_function = len if length_function is None else length_function

    def as_dict(self):
        return {
            "chunk_size": self.chunk_size,
            "chunk_overlap": self.chunk_overlap,
            "length_function": self.length_function,
        }


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
