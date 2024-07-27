from abc import ABC
from typing import Optional

class BaseEmbederConfig(ABC):
    """
    Config for Embeder.
    """

    def __init__(
        self,
        model: Optional[str] = None,
        dims: Optional[int] = None,
    ):
        """
        Initializes a configuration class instance for the Embeder.

        :param model: Controls the embedding model used, defaults to None
        :type model: Optional[str], optional
        :param dims: Controls the dimensionality of the embedding, defaults to None
        :type dims: Optional[int], optional
        """
        
        self.model = model