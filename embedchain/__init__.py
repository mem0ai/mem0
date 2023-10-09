import importlib.metadata

__version__ = importlib.metadata.version(__package__ or __name__)

from embedchain.apps.app import App  # noqa: F401
from embedchain.apps.custom_app import CustomApp  # noqa: F401
from embedchain.apps.Llama2App import Llama2App  # noqa: F401
from embedchain.apps.open_source_app import OpenSourceApp  # noqa: F401
from embedchain.apps.person_app import (PersonApp,  # noqa: F401
                                       PersonOpenSourceApp)
from embedchain.vectordb.chroma import ChromaDB  # noqa: F401
