import importlib.metadata

try:
    __version__ = importlib.metadata.version("mem0ai")
except (importlib.metadata.PackageNotFoundError, Exception):
    __version__ = "2.0.18"

from mem0.client.main import AsyncMemoryClient, MemoryClient  # noqa
from mem0.memory.main import AsyncMemory, Memory  # noqa
