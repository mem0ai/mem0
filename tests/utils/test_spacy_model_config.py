"""
Tests for configurable spaCy model support in entity extraction and lemmatization.

Ensures that spacy_model parameter is correctly threaded through the call stack
from MemoryConfig down to spacy.load() calls without requiring actual model downloads.
All tests mock sys.modules['spacy'] to avoid dependencies on installed models.
"""

import pytest
import sys
from unittest.mock import MagicMock, patch


class TestSpacyModelConfig:
    """Test spaCy model configuration propagation."""

    def test_memory_config_has_spacy_model_field_default(self):
        """MemoryConfig has spacy_model field with default value."""
        from mem0.configs.base import MemoryConfig

        config = MemoryConfig()
        assert hasattr(config, "spacy_model")
        assert config.spacy_model == "en_core_web_sm"

    def test_memory_config_accepts_custom_spacy_model(self):
        """MemoryConfig accepts custom spacy_model value."""
        from mem0.configs.base import MemoryConfig

        config = MemoryConfig(spacy_model="es_core_news_sm")
        assert config.spacy_model == "es_core_news_sm"

    def test_get_nlp_full_forwards_model_name(self):
        """get_nlp_full() correctly forwards model_name to spacy.load()."""
        # Mock spacy before importing spacy_models
        mock_spacy = MagicMock()
        mock_spacy.util.is_package.return_value = True
        mock_nlp = MagicMock()
        mock_spacy.load.return_value = mock_nlp

        with patch.dict(sys.modules, {'spacy': mock_spacy}):
            from mem0.utils.spacy_models import get_nlp_full, _nlp_full_cache, _load_failed_full

            # Clear caches
            _nlp_full_cache.clear()
            _load_failed_full.clear()

            # Call with custom model name
            model_name = "custom_model_sm"
            result = get_nlp_full(model_name=model_name)

            # Verify spacy.load was called with correct model name
            mock_spacy.load.assert_called_once_with(model_name)
            assert result == mock_nlp

    def test_get_nlp_lemma_forwards_model_name(self):
        """get_nlp_lemma() correctly forwards model_name to spacy.load()."""
        # Mock spacy before importing
        mock_spacy = MagicMock()
        mock_spacy.util.is_package.return_value = True
        mock_nlp = MagicMock()
        mock_spacy.load.return_value = mock_nlp

        with patch.dict(sys.modules, {'spacy': mock_spacy}):
            from mem0.utils.spacy_models import get_nlp_lemma, _nlp_lemma_cache, _load_failed_lemma

            # Clear caches
            _nlp_lemma_cache.clear()
            _load_failed_lemma.clear()

            # Call with custom model name
            model_name = "fr_core_news_sm"
            result = get_nlp_lemma(model_name=model_name)

            # Verify spacy.load was called with correct model name and disable list
            mock_spacy.load.assert_called_once_with(model_name, disable=["ner", "parser"])
            assert result == mock_nlp

    def test_get_nlp_full_caches_by_model_name(self):
        """get_nlp_full() maintains separate caches for different model names."""
        # Mock spacy
        mock_spacy = MagicMock()
        mock_spacy.util.is_package.return_value = True
        mock_nlp1 = MagicMock()
        mock_nlp2 = MagicMock()
        mock_spacy.load.side_effect = [mock_nlp1, mock_nlp2]

        with patch.dict(sys.modules, {'spacy': mock_spacy}):
            from mem0.utils.spacy_models import get_nlp_full, _nlp_full_cache, _load_failed_full

            # Clear caches
            _nlp_full_cache.clear()
            _load_failed_full.clear()

            # Load two different models
            result1 = get_nlp_full(model_name="model1")
            result2 = get_nlp_full(model_name="model2")

            # Verify both are cached separately
            assert result1 == mock_nlp1
            assert result2 == mock_nlp2
            assert _nlp_full_cache.get("model1") == mock_nlp1
            assert _nlp_full_cache.get("model2") == mock_nlp2

    def test_extract_entities_forwards_model_name(self):
        """extract_entities() forwards spacy_model parameter to get_nlp_full()."""
        # Mock spacy
        mock_spacy = MagicMock()
        mock_spacy.util.is_package.return_value = True
        mock_doc = MagicMock()
        mock_doc.text = "sample text"
        mock_doc.__iter__ = MagicMock(return_value=iter([]))
        mock_doc.noun_chunks = []
        mock_nlp = MagicMock()
        mock_nlp.return_value = mock_doc
        mock_spacy.load.return_value = mock_nlp

        with patch.dict(sys.modules, {'spacy': mock_spacy}):
            from mem0.utils.entity_extraction import extract_entities
            from mem0.utils import spacy_models

            # Clear caches
            spacy_models._nlp_full_cache.clear()
            spacy_models._load_failed_full.clear()

            # Call with custom model
            model_name = "de_core_news_sm"
            extract_entities("sample text", spacy_model=model_name)

            # Verify spacy.load was called with correct model
            mock_spacy.load.assert_called_with(model_name)

    def test_lemmatize_for_bm25_forwards_model_name(self):
        """lemmatize_for_bm25() forwards spacy_model parameter to get_nlp_lemma()."""
        # Mock spacy
        mock_spacy = MagicMock()
        mock_spacy.util.is_package.return_value = True
        mock_token = MagicMock()
        mock_token.is_punct = False
        mock_token.is_stop = False
        mock_token.lemma_ = "test"
        mock_token.text = "testing"
        mock_doc = MagicMock()
        mock_doc.__iter__ = MagicMock(return_value=iter([mock_token]))
        mock_nlp = MagicMock()
        mock_nlp.return_value = mock_doc
        mock_spacy.load.return_value = mock_nlp

        with patch.dict(sys.modules, {'spacy': mock_spacy}):
            from mem0.utils.lemmatization import lemmatize_for_bm25
            from mem0.utils import spacy_models

            # Clear caches
            spacy_models._nlp_lemma_cache.clear()
            spacy_models._load_failed_lemma.clear()

            # Call with custom model
            model_name = "it_core_news_sm"
            lemmatize_for_bm25("sample text", spacy_model=model_name)

            # Verify spacy.load was called with correct model and disable list
            mock_spacy.load.assert_called_with(model_name, disable=["ner", "parser"])

    def test_ensure_model_available_accepts_model_name(self):
        """_ensure_model_available() accepts model_name parameter."""
        # Mock spacy
        mock_spacy = MagicMock()
        mock_spacy.util.is_package.return_value = True

        with patch.dict(sys.modules, {'spacy': mock_spacy}):
            from mem0.utils.spacy_models import _ensure_model_available

            # Should not raise for existing model
            _ensure_model_available("en_core_web_sm")
            mock_spacy.util.is_package.assert_called_with("en_core_web_sm")

            # Reset and test custom model
            mock_spacy.util.is_package.reset_mock()
            _ensure_model_available("pt_core_news_sm")
            mock_spacy.util.is_package.assert_called_with("pt_core_news_sm")

    def test_extract_entities_batch_forwards_model_name(self):
        """extract_entities_batch() forwards spacy_model parameter to get_nlp_full()."""
        # Mock spacy
        mock_spacy = MagicMock()
        mock_spacy.util.is_package.return_value = True
        mock_doc = MagicMock()
        mock_doc.text = "sample"
        mock_doc.__iter__ = MagicMock(return_value=iter([]))
        mock_doc.noun_chunks = []
        mock_nlp = MagicMock()
        mock_nlp.pipe = MagicMock(return_value=[mock_doc])
        mock_spacy.load.return_value = mock_nlp

        with patch.dict(sys.modules, {'spacy': mock_spacy}):
            from mem0.utils.entity_extraction import extract_entities_batch
            from mem0.utils import spacy_models

            # Clear caches
            spacy_models._nlp_full_cache.clear()
            spacy_models._load_failed_full.clear()

            # Call with custom model
            model_name = "zh_core_web_sm"
            extract_entities_batch(["text1", "text2"], spacy_model=model_name)

            # Verify spacy.load was called with correct model
            mock_spacy.load.assert_called_with(model_name)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
