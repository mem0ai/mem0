import os  # noqa: F401
from typing import Any, Dict

from gptcache import cache
from gptcache.adapter.adapter import adapt  # noqa: F401
from gptcache.config import Config  # noqa: F401
from gptcache.manager import get_data_manager
from gptcache.manager.scalar_data.base import Answer
from gptcache.manager.scalar_data.base import DataType as CacheDataType
from gptcache.similarity_evaluation.distance import \
    SearchDistanceEvaluation  # noqa: F401


def gptcache_pre_function(data: Dict[str, Any], **params: Dict[str, Any]):  # noqa: F401
    return data["input_query"]


def gptcache_data_manager(vector_dimension):  # noqa: F401
    # if not os.path.exists("./.cache/"):
    #     os.mkdir("./.cache/")
    return get_data_manager(
        cache_base="sqlite", vector_base="chromadb", max_size=1000, eviction="LRU", data_path="data_map.txt"
    )


def gptcache_data_convert(cache_data):
    print("Cache hits!!!!!!!!")
    return cache_data


def gptcache_update_cache_callback(llm_data, update_cache_func, *args, **kwargs):  # noqa: F401
    print("Cache Misss!!!!!!")
    update_cache_func(Answer(llm_data, CacheDataType.STR))
    return llm_data


cache = cache
