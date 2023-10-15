import importlib.metadata

#__version__ = importlib.metadata.version(__package__ or __name__)
__version__ = importlib.metadata.version("embedchain")


from embedchain.apps.app import App  # noqa: F401
from embedchain.apps.custom_app import CustomApp  # noqa: F401
from apps.llama2_app import llama2_app  # noqa: F401
from embedchain.apps.open_source_app import OpenSourceApp  # noqa: F401
from embedchain.apps.person_app import (PersonApp,  # noqa: F401
                                        PersonOpenSourceApp)
from embedchain.vectordb.chroma import ChromaDB  # noqa: F401
