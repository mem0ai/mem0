import importlib.metadata

__version__ = importlib.metadata.version(__package__ or __name__)

from embedchain.apps.App import App  # noqa: F401
from embedchain.apps.OpenSourceApp import OpenSourceApp  # noqa: F401
from embedchain.apps.PersonApp import (PersonApp,  # noqa: F401
                                       PersonOpenSourceApp)
