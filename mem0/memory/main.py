import asyncio
import concurrent.futures
import gc
import hashlib
import json
import logging
import os
import time
import uuid
import warnings
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union

import pydantic
import pydantic_core

from mem0.captures.main import CapturesManager
from mem0.configs.base import (AsyncMemoryConfig, MemoryConfig)
from mem0.configs.vector_stores.base import VectorStoreConfig
from mem0.memory.base import MemoryBase
from mem0.memory.graph_memory import MemoryGraph
from mem0.memory.utils import (
    get_fact_retrieval_messages,
    get_update_memory_messages,
)
from mem0.utils.factory import EmbedderFactory, LlmFactory, VectorStoreFactory

logger = logging.getLogger(__name__)
