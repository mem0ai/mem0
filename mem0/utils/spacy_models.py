"""
Shared spaCy model loader.

Consolidates spaCy model loading into a single module so that
entity_extraction and lemmatization share one instance instead of
each loading their own copy from disk.
"""

import logging
import threading

logger = logging.getLogger(__name__)

_nlp_full_cache = {}
_nlp_lemma_cache = {}
_load_failed_full = set()
_load_failed_lemma = set()
_lock = threading.Lock()


def _ensure_model_available(model_name: str = "en_core_web_sm"):
    """Download spaCy model if installed but missing."""
    try:
        import spacy
    except ImportError:
        raise ImportError(
            "spaCy is not installed. Install it with: pip install mem0ai[nlp]"
        )

    if not spacy.util.is_package(model_name):
        logger.info(f"Downloading spaCy model {model_name}...")
        try:
            from spacy.cli import download

            download(model_name)
            logger.info(f"spaCy model {model_name} downloaded successfully")
        except Exception as e:
            raise RuntimeError(
                f"Failed to download spaCy model {model_name}: {e}. "
                f"Please install manually: python -m spacy download {model_name}"
            ) from e


def get_nlp_full(model_name: str = "en_core_web_sm"):
    """Return spaCy model with all pipelines (NER, tagger, etc.) for entity extraction.

    Args:
        model_name: spaCy model to load (default: "en_core_web_sm")

    Returns:
        spaCy Language model or None if loading fails.
    """
    global _nlp_full_cache, _load_failed_full
    if model_name in _load_failed_full:
        return None
    if model_name in _nlp_full_cache:
        return _nlp_full_cache[model_name]
    with _lock:
        if model_name in _nlp_full_cache:
            return _nlp_full_cache[model_name]
        if model_name in _load_failed_full:
            return None
        try:
            _ensure_model_available(model_name)
            import spacy

            nlp = spacy.load(model_name)
            _nlp_full_cache[model_name] = nlp
            logger.info(f"spaCy full model '{model_name}' loaded")
        except Exception as e:
            logger.warning(f"Failed to load spaCy full model '{model_name}': {e}")
            _load_failed_full.add(model_name)
            return None
    return _nlp_full_cache.get(model_name)


def get_nlp_lemma(model_name: str = "en_core_web_sm"):
    """Return spaCy model with only lemmatizer for BM25 text processing.

    Args:
        model_name: spaCy model to load (default: "en_core_web_sm")

    Returns:
        spaCy Language model or None if loading fails.
    """
    global _nlp_lemma_cache, _load_failed_lemma
    if model_name in _load_failed_lemma:
        return None
    if model_name in _nlp_lemma_cache:
        return _nlp_lemma_cache[model_name]
    with _lock:
        if model_name in _nlp_lemma_cache:
            return _nlp_lemma_cache[model_name]
        if model_name in _load_failed_lemma:
            return None
        try:
            _ensure_model_available(model_name)
            import spacy

            nlp = spacy.load(model_name, disable=["ner", "parser"])
            _nlp_lemma_cache[model_name] = nlp
            logger.info(f"spaCy lemma model '{model_name}' loaded")
        except Exception as e:
            logger.warning(f"Failed to load spaCy lemma model '{model_name}': {e}")
            _load_failed_lemma.add(model_name)
            return None
    return _nlp_lemma_cache.get(model_name)
