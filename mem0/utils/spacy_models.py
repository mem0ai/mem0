"""
Shared spaCy model loader.

Consolidates spaCy model loading into a single module so that
entity_extraction and lemmatization share one instance instead of
each loading their own copy from disk.
"""

import logging
import os
import threading

logger = logging.getLogger(__name__)

# 语言代码 → spaCy 模型名映射
SPACY_MODEL_MAP: dict[str, str] = {
    "en": "en_core_web_sm",
    "zh": "zh_core_web_sm",
}

_nlp_full_cache: dict[str, object] = {}
_nlp_lemma_cache: dict[str, object] = {}
_load_failed: set[str] = set()
_lock = threading.Lock()


def _get_model_name() -> str:
    """从环境变量获取 spaCy 模型名。

    支持语言代码（查 SPACY_MODEL_MAP）或完整模型名。
    默认返回 en_core_web_sm。
    """
    val = os.environ.get("MEM0_SPACY_MODEL", "en_core_web_sm")
    return SPACY_MODEL_MAP.get(val, val)


def _ensure_model_available(model_name: str):
    """检查并下载指定 spaCy 模型（如缺失）。"""
    try:
        import spacy
    except ImportError:
        raise ImportError(
            "spaCy is not installed. Install it with: pip install mem0ai[nlp]"
        )

    if not spacy.util.is_package(model_name):
        logger.info("Downloading spaCy model %s...", model_name)
        try:
            from spacy.cli import download

            download(model_name)
            logger.info("spaCy model %s downloaded successfully", model_name)
        except (Exception, SystemExit) as e:
            raise RuntimeError(
                f"Failed to download spaCy model {model_name}: {e}. "
                f"Please install manually: python -m spacy download {model_name}"
            ) from e


def get_nlp_full():
    """返回 spaCy 完整模型（NER、tagger 等），用于实体提取。"""
    model_name = _get_model_name()
    global _nlp_full_cache, _load_failed

    if model_name in _load_failed:
        return None
    cached = _nlp_full_cache.get(model_name)
    if cached is not None:
        return cached

    with _lock:
        if model_name in _load_failed:
            return None
        cached = _nlp_full_cache.get(model_name)
        if cached is not None:
            return cached

        try:
            _ensure_model_available(model_name)
            import spacy

            _nlp_full_cache[model_name] = spacy.load(model_name)
            logger.info("spaCy full model loaded: %s", model_name)
        except Exception as e:
            logger.warning("Failed to load spaCy full model %s: %s", model_name, e)
            _load_failed.add(model_name)
            return None

    return _nlp_full_cache[model_name]


def get_nlp_lemma():
    """返回 spaCy 模型（仅 lemmatizer），用于 BM25 文本处理。"""
    model_name = _get_model_name()
    global _nlp_lemma_cache, _load_failed

    if model_name in _load_failed:
        return None
    cached = _nlp_lemma_cache.get(model_name)
    if cached is not None:
        return cached

    with _lock:
        if model_name in _load_failed:
            return None
        cached = _nlp_lemma_cache.get(model_name)
        if cached is not None:
            return cached

        try:
            _ensure_model_available(model_name)
            import spacy

            _nlp_lemma_cache[model_name] = spacy.load(
                model_name, disable=["ner", "parser"]
            )
            logger.info("spaCy lemma model loaded: %s", model_name)
        except Exception as e:
            logger.warning("Failed to load spaCy lemma model %s: %s", model_name, e)
            _load_failed.add(model_name)
            return None

    return _nlp_lemma_cache[model_name]
