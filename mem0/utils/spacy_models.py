"""
Shared spaCy model loader.

Entity extraction and English lemmatization can use different configured
pipelines. Defaults stay on en_core_web_sm for backward compatibility.
"""

from __future__ import annotations

import logging
import os
import threading
from typing import Any

logger = logging.getLogger(__name__)

_DEFAULT_MODEL = "en_core_web_sm"
_MODEL_ENV = "MEM0_SPACY_MODEL"
_ENTITY_MODEL_ENV = "MEM0_SPACY_ENTITY_MODEL"
_LEMMA_MODEL_ENV = "MEM0_SPACY_LEMMA_MODEL"

_nlp_cache: dict[tuple[str, tuple[str, ...]], Any] = {}
_load_failed: set[tuple[str, tuple[str, ...]]] = set()
_lock = threading.Lock()


def _get_env_model_name(env_var: str) -> str | None:
    model_name = os.getenv(env_var)
    if model_name is None:
        return None

    model_name = model_name.strip()
    return model_name or None


def _get_model_name(kind: str) -> str:
    base_model = _get_env_model_name(_MODEL_ENV) or _DEFAULT_MODEL
    if kind == "full":
        return _get_env_model_name(_ENTITY_MODEL_ENV) or base_model
    if kind == "lemma":
        return _get_env_model_name(_LEMMA_MODEL_ENV) or base_model
    raise ValueError(f"Unknown spaCy model kind: {kind}")


def _reset_model_cache() -> None:
    """Clear model loader state for tests."""
    with _lock:
        _nlp_cache.clear()
        _load_failed.clear()


def _import_spacy():
    try:
        import spacy
    except ImportError:
        raise ImportError("spaCy is not installed. Install it with: pip install mem0ai[nlp]")
    return spacy


def _ensure_default_model_available(spacy, model_name: str) -> None:
    if model_name != _DEFAULT_MODEL:
        return

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


def _load_model(kind: str, disable: tuple[str, ...] = ()):
    model_name = _get_model_name(kind)
    cache_key = (model_name, disable)
    if cache_key in _load_failed:
        return None
    if cache_key in _nlp_cache:
        return _nlp_cache[cache_key]

    with _lock:
        if cache_key in _nlp_cache:
            return _nlp_cache[cache_key]
        if cache_key in _load_failed:
            return None

        try:
            spacy = _import_spacy()
            _ensure_default_model_available(spacy, model_name)
            nlp = spacy.load(model_name, disable=list(disable))
            _nlp_cache[cache_key] = nlp
            logger.info("spaCy %s model loaded: %s", kind, model_name)
            return nlp
        except Exception as e:
            logger.warning(
                "Failed to load spaCy %s model %s: %s. "
                "Please install manually: python -m spacy download %s",
                kind,
                model_name,
                e,
                model_name,
            )
            _load_failed.add(cache_key)
            return None


def get_nlp_full():
    """Return spaCy model with all pipelines for entity extraction."""
    return _load_model("full")


def get_nlp_lemma():
    """Return spaCy model with only lemmatizer-relevant components for BM25."""
    return _load_model("lemma", disable=("ner", "parser"))
