"""
Shared spaCy model loader.

Consolidates spaCy model loading into a single module so that
entity_extraction and lemmatization share one instance instead of
each loading their own copy from disk.

The model defaults to ``en_core_web_sm`` and can be overridden with the
``MEM0_SPACY_MODEL`` environment variable so non-English users can pick a
language-specific pipeline (e.g. ``zh_core_web_sm``, ``ja_core_news_sm``,
``de_core_news_sm``).
"""

import logging
import os
import threading

logger = logging.getLogger(__name__)

_DEFAULT_MODEL = "en_core_web_sm"

_nlp_full = None
_nlp_lemma = None
_load_failed_full = False
_load_failed_lemma = False
_lock = threading.Lock()


def _spacy_model_name() -> str:
    """Return the configured spaCy model name (env override, default English)."""
    return os.environ.get("MEM0_SPACY_MODEL", "").strip() or _DEFAULT_MODEL


def _ensure_model_available():
    """Download the configured spaCy model if spaCy is installed but it is missing."""
    model = _spacy_model_name()
    try:
        import spacy
    except ImportError:
        raise ImportError("spaCy is not installed. Install it with: pip install mem0ai[nlp]")

    if not spacy.util.is_package(model):
        logger.info(f"Downloading spaCy model {model}...")
        try:
            from spacy.cli import download

            download(model)
            logger.info(f"spaCy model {model} downloaded successfully")
        except Exception as e:
            raise RuntimeError(
                f"Failed to download spaCy model {model}: {e}. "
                f"Please install manually: python -m spacy download {model}"
            ) from e


def get_nlp_full():
    """Return spaCy model with all pipelines (NER, tagger, etc.) for entity extraction."""
    global _nlp_full, _load_failed_full
    if _load_failed_full:
        return None
    if _nlp_full is not None:
        return _nlp_full
    with _lock:
        if _nlp_full is not None:
            return _nlp_full
        if _load_failed_full:
            return None
        try:
            _ensure_model_available()
            import spacy

            _nlp_full = spacy.load(_spacy_model_name())
            logger.info("spaCy full model loaded")
        except Exception as e:
            logger.warning(f"Failed to load spaCy full model: {e}")
            _load_failed_full = True
            return None
    return _nlp_full


def get_nlp_lemma():
    """Return spaCy model with only lemmatizer for BM25 text processing."""
    global _nlp_lemma, _load_failed_lemma
    if _load_failed_lemma:
        return None
    if _nlp_lemma is not None:
        return _nlp_lemma
    with _lock:
        if _nlp_lemma is not None:
            return _nlp_lemma
        if _load_failed_lemma:
            return None
        try:
            _ensure_model_available()
            import spacy

            _nlp_lemma = spacy.load(_spacy_model_name(), disable=["ner", "parser"])
            logger.info("spaCy lemma model loaded")
        except Exception as e:
            logger.warning(f"Failed to load spaCy lemma model: {e}")
            _load_failed_lemma = True
            return None
    return _nlp_lemma
