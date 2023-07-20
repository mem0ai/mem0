import importlib.metadata

__version__ = importlib.metadata.version(__package__ or __name__)

from embedchain.apps.App import App  # noqa: F401
from embedchain.apps.CustomApp import CustomApp  # noqa: F401
from embedchain.apps.Llama2App import Llama2App  # noqa: F401
from embedchain.apps.OpenSourceApp import OpenSourceApp  # noqa: F401
from embedchain.apps.PersonApp import (PersonApp,  # noqa: F401
                                       PersonOpenSourceApp)
