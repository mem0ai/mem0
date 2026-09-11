import importlib.metadata

try:
    __version__ = importlib.metadata.version("mem0ai")
except importlib.metadata.PackageNotFoundError:
    # Running from a source checkout (pytest uses pythonpath = ["."]), a vendored
    # copy, or a container that copied mem0/ in without installing the dist.
    __version__ = "0.0.0+unknown"

from mem0.client.main import AsyncMemoryClient, MemoryClient  # noqa
from mem0.memory.main import AsyncMemory, Memory  # noqa
