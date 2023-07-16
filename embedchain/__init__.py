import importlib.metadata

__version__ = importlib.metadata.version(__package__ or __name__)

from .embedchain import (
    App,  # noqa: F401
    OpenSourceApp,  # noqa: F401
    PersonApp,  # noqa: F401
    PersonOpenSourceApp,  # noqa: F401
)
