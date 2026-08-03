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

_DEFAULT_MODEL = "en_core_web_sm"


def _get_model_name() -> str:
    """Return the spaCy model name, overridable via the MEM0_SPACY_MODEL env var."""
    return os.getenv("MEM0_SPACY_MODEL", _DEFAULT_MODEL)

_nlp_full = None
_nlp_lemma = None
_load_failed_full = False
_load_failed_lemma = False
_lock = threading.Lock()


def _ensure_model_available():
    """Download the configured spaCy model if spaCy is installed but the model is missing."""
    try:
        import spacy
    except ImportError:
        raise ImportError(
            "spaCy is not installed. Install it with: pip install mem0ai[nlp]"
        )

    model_name = _get_model_name()
    if not spacy.util.is_package(model_name):
        logger.info("Downloading spaCy model %s...", model_name)
        try:
            from spacy.cli import download

            download(model_name)
            logger.info("spaCy model %s downloaded successfully", model_name)
        except Exception as e:
            raise RuntimeError(
                f"Failed to download spaCy model {model_name}: {e}. "
                f"Please install manually: python -m spacy download {model_name}"
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

            _nlp_full = spacy.load(_get_model_name())
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

            _nlp_lemma = spacy.load(_get_model_name(), disable=["ner", "parser"])
            logger.info("spaCy lemma model loaded")
        except Exception as e:
            logger.warning(f"Failed to load spaCy lemma model: {e}")
            _load_failed_lemma = True
            return None
    return _nlp_lemma
