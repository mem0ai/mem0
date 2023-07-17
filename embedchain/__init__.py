import importlib.metadata

__version__ = importlib.metadata.version(__package__ or __name__)

from .embedchain import App  # noqa: F401
from .embedchain import OpenSourceApp  # noqa: F401
from .embedchain import PersonApp  # noqa: F401
from .embedchain import PersonOpenSourceApp  # noqa: F401
