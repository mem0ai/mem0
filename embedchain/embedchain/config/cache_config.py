from typing import Any, Optional

from embedchain.config.base_config import BaseConfig
from embedchain.helpers.json_serializable import register_deserializable


@register_deserializable
class CacheSimilarityEvalConfig(BaseConfig):
    """
    This is the evaluator to compare two embeddings according to their distance computed in embedding retrieval stage.
    In the retrieval stage, `search_result` is the distance used for approximate nearest neighbor search and have been
    put into `cache_dict`. `max_distance` is used to bound this distance to make it between [0-`max_distance`].
    `positive` is used to indicate this distance is directly proportional to the similarity of two entities.
    If `positive` is set `False`, `max_distance` will be used to subtract this distance to get the final score.

    :param max_distance: the bound of maximum distance.
    :type max_distance: float
    :param positive: if the larger distance indicates more similar of two entities, It is True. Otherwise, it is False.
    :type positive: bool
    """

    def __init__(
        self,
        strategy: Optional[str] = "distance",
        max_distance: Optional[float] = 1.0,
        positive: Optional[bool] = False,
    ):
        self.strategy = strategy
        self.max_distance = max_distance
        self.positive = positive

    @staticmethod
    def from_config(config: Optional[dict[str, Any]]):
        if config is None:
            return CacheSimilarityEvalConfig()
        else:
            return CacheSimilarityEvalConfig(
                strategy=config.get("strategy", "distance"),
                max_distance=config.get("max_distance", 1.0),
                positive=config.get("positive", False),
            )


@register_deserializable
class CacheInitConfig(BaseConfig):
    """
    This is a cache init config. Used to initialize a cache.

    :param similarity_threshold: a threshold ranged from 0 to 1 to filter search results with similarity score higher \
     than the threshold. When it is 0, there is no hits. When it is 1, all search results will be returned as hits.
    :type similarity_threshold: float
    :param auto_flush: it will be automatically flushed every time xx pieces of data are added, default to 20
    :type auto_flush: int
    """

    def __init__(
        self,
        similarity_threshold: Optional[float] = 0.8,
        auto_flush: Optional[int] = 20,
    ):
        if similarity_threshold < 0 or similarity_threshold > 1:
            raise ValueError(f"similarity_threshold {similarity_threshold} should be between 0 and 1")

        self.similarity_threshold = similarity_threshold
        self.auto_flush = auto_flush

    @staticmethod
    def from_config(config: Optional[dict[str, Any]]):
        if config is None:
            return CacheInitConfig()
        else:
            return CacheInitConfig(
                similarity_threshold=config.get("similarity_threshold", 0.8),
                auto_flush=config.get("auto_flush", 20),
            )


@register_deserializable
class CacheConfig(BaseConfig):
    def __init__(
        self,
        similarity_eval_config: Optional[CacheSimilarityEvalConfig] = CacheSimilarityEvalConfig(),
        init_config: Optional[CacheInitConfig] = CacheInitConfig(),
    ):
        self.similarity_eval_config = similarity_eval_config
        self.init_config = init_config

    @staticmethod
    def from_config(config: Optional[dict[str, Any]]):
        if config is None:
            return CacheConfig()
        else:
            return CacheConfig(
                similarity_eval_config=CacheSimilarityEvalConfig.from_config(config.get("similarity_evaluation", {})),
                init_config=CacheInitConfig.from_config(config.get("init_config", {})),
            )
