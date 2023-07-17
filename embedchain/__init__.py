import importlib.metadata

__version__ = importlib.metadata.version(__package__ or __name__)

from embedchain.Apps.App import App  # noqa: F401
from embedchain.Apps.OpenSourceApp import OpenSourceApp  # noqa: F401
from embedchain.Apps.PersonApp import (PersonApp,  # noqa: F401
                                       PersonOpenSourceApp)
