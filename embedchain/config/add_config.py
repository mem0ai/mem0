import builtins
import logging
from collections.abc import Callable
from importlib import import_module
from typing import Optional

from embedchain.config.base_config import BaseConfig
from embedchain.helpers.json_serializable import register_deserializable


@register_deserializable
class ChunkerConfig(BaseConfig):
    """
    Config for the chunker used in `add` method
    """

    def __init__(
        self,
        chunk_size: Optional[int] = 2000,
        chunk_overlap: Optional[int] = 0,
        length_function: Optional[Callable[[str], int]] = None,
        min_chunk_size: Optional[int] = 0,
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.min_chunk_size = min_chunk_size
        if self.min_chunk_size >= self.chunk_size:
            raise ValueError(f"min_chunk_size {min_chunk_size} should be less than chunk_size {chunk_size}")
        if self.min_chunk_size < self.chunk_overlap:
            logging.warning(
                f"min_chunk_size {min_chunk_size} should be greater than chunk_overlap {chunk_overlap}, otherwise it is redundant."  # noqa:E501
            )

        if isinstance(length_function, str):
            self.length_function = self.load_func(length_function)
        else:
            self.length_function = length_function if length_function else len

    @staticmethod
    def load_func(dotpath: str):
        if "." not in dotpath:
            return getattr(builtins, dotpath)
        else:
            module_, func = dotpath.rsplit(".", maxsplit=1)
            m = import_module(module_)
            return getattr(m, func)


@register_deserializable
class LoaderConfig(BaseConfig):
    """
    Config for the loader used in `add` method
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
