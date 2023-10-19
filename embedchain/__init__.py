import importlib.metadata

__version__ = importlib.metadata.version(__package__ or __name__)

from embedchain.apps.app import App  # noqa: F401
from embedchain.vectordb.chroma import ChromaDB  # noqa: F401
