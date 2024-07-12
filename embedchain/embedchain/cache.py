import logging
import os  # noqa: F401
from typing import Any

from gptcache import cache  # noqa: F401
from gptcache.adapter.adapter import adapt  # noqa: F401
from gptcache.config import Config  # noqa: F401
from gptcache.manager import get_data_manager
from gptcache.manager.scalar_data.base import Answer
from gptcache.manager.scalar_data.base import DataType as CacheDataType
from gptcache.session import Session
from gptcache.similarity_evaluation.distance import \
    SearchDistanceEvaluation  # noqa: F401
from gptcache.similarity_evaluation.exact_match import \
    ExactMatchEvaluation  # noqa: F401

logger = logging.getLogger(__name__)


def gptcache_pre_function(data: dict[str, Any], **params: dict[str, Any]):
    return data["input_query"]


def gptcache_data_manager(vector_dimension):
    return get_data_manager(cache_base="sqlite", vector_base="chromadb", max_size=1000, eviction="LRU")


def gptcache_data_convert(cache_data):
    logger.info("[Cache] Cache hit, returning cache data...")
    return cache_data


def gptcache_update_cache_callback(llm_data, update_cache_func, *args, **kwargs):
    logger.info("[Cache] Cache missed, updating cache...")
    update_cache_func(Answer(llm_data, CacheDataType.STR))
    return llm_data


def _gptcache_session_hit_func(cur_session_id: str, cache_session_ids: list, cache_questions: list, cache_answer: str):
    return cur_session_id in cache_session_ids


def get_gptcache_session(session_id: str):
    return Session(name=session_id, check_hit_func=_gptcache_session_hit_func)
