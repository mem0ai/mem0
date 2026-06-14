from unittest.mock import MagicMock, patch

import pytest

from mem0.configs.rerankers.base import BaseRerankerConfig
from mem0.configs.rerankers.huggingface import HuggingFaceRerankerConfig


class TestHuggingFaceRerankerConfig:
    def test_default_config(self):
        config = HuggingFaceRerankerConfig()
        assert config.model == "BAAI/bge-reranker-base"
        assert config.device is None
        assert config.batch_size == 32
        assert config.max_length == 512
        assert config.normalize is True
        assert config.top_k is None
        assert config.provider is None
        assert config.api_key is None

    def test_custom_values(self):
        config = HuggingFaceRerankerConfig(
            model="cross-encoder/ms-marco-MiniLM-L-6-v2",
            device="cuda",
            batch_size=16,
            max_length=256,
            normalize=False,
            top_k=5,
        )
        assert config.model == "cross-encoder/ms-marco-MiniLM-L-6-v2"
        assert config.device == "cuda"
        assert config.batch_size == 16
        assert config.max_length == 256
        assert config.normalize is False
        assert config.top_k == 5

    def test_partial_override(self):
        config = HuggingFaceRerankerConfig(batch_size=8)
        assert config.model == "BAAI/bge-reranker-base"  # default preserved
        assert config.batch_size == 8  # overridden
        assert config.normalize is True  # default preserved


class TestHuggingFaceRerankerInit:
    @pytest.fixture
    def mock_hf_components(self):
        with (
            patch("mem0.reranker.huggingface_reranker.AutoTokenizer") as mock_tokenizer_cls,
            patch("mem0.reranker.huggingface_reranker.AutoModelForSequenceClassification") as mock_model_cls,
            patch("mem0.reranker.huggingface_reranker.torch") as mock_torch,
        ):
            mock_tokenizer = MagicMock()
            mock_tokenizer_cls.from_pretrained.return_value = mock_tokenizer

            mock_model = MagicMock()
            mock_model_cls.from_pretrained.return_value = mock_model

            mock_torch.cuda.is_available.return_value = False

            yield {
                "tokenizer_cls": mock_tokenizer_cls,
                "model_cls": mock_model_cls,
                "tokenizer": mock_tokenizer,
                "model": mock_model,
                "torch": mock_torch,
            }

    def test_init_from_dict(self, mock_hf_components):
        from mem0.reranker.huggingface_reranker import HuggingFaceReranker

        reranker = HuggingFaceReranker({"model": "test-model", "batch_size": 16})

        assert isinstance(reranker.config, HuggingFaceRerankerConfig)
        assert reranker.config.model == "test-model"
        assert reranker.config.batch_size == 16
        assert reranker.device == "cpu"

    def test_init_from_huggingface_config(self, mock_hf_components):
        from mem0.reranker.huggingface_reranker import HuggingFaceReranker

        config = HuggingFaceRerankerConfig(model="my-model", device="cuda")
        reranker = HuggingFaceReranker(config)

        assert reranker.device == "cuda"

    def test_init_from_base_config_converts(self, mock_hf_components):
        from mem0.reranker.huggingface_reranker import HuggingFaceReranker

        base_config = BaseRerankerConfig(provider="huggingface", top_k=5)
        reranker = HuggingFaceReranker(base_config)

        assert isinstance(reranker.config, HuggingFaceRerankerConfig)
        assert reranker.config.top_k == 5
        assert reranker.config.device is None
        assert reranker.config.batch_size == 32

    def test_init_from_base_config_preserves_model(self, mock_hf_components):
        from mem0.reranker.huggingface_reranker import HuggingFaceReranker

        base_config = BaseRerankerConfig(model="custom-model")
        reranker = HuggingFaceReranker(base_config)

        assert reranker.config.model == "custom-model"

    def test_init_auto_detects_cuda(self, mock_hf_components):
        from mem0.reranker.huggingface_reranker import HuggingFaceReranker

        mock_hf_components["torch"].cuda.is_available.return_value = True

        reranker = HuggingFaceReranker({"model": "test"})

        assert reranker.device == "cuda"

    def test_explicit_device_overrides_auto_detect(self, mock_hf_components):
        from mem0.reranker.huggingface_reranker import HuggingFaceReranker

        mock_hf_components["torch"].cuda.is_available.return_value = True

        reranker = HuggingFaceReranker({"model": "test", "device": "cpu"})

        assert reranker.device == "cpu"

    def test_model_loaded_and_set_to_eval(self, mock_hf_components):
        from mem0.reranker.huggingface_reranker import HuggingFaceReranker

        HuggingFaceReranker({"model": "test-model"})

        mock_hf_components["tokenizer_cls"].from_pretrained.assert_called_once_with("test-model")
        mock_hf_components["model_cls"].from_pretrained.assert_called_once_with("test-model")
        mock_hf_components["model"].to.assert_called_once_with("cpu")
        mock_hf_components["model"].eval.assert_called_once()

    def test_import_error_when_transformers_missing(self):
        from mem0.reranker.huggingface_reranker import HuggingFaceReranker

        with patch("mem0.reranker.huggingface_reranker.TRANSFORMERS_AVAILABLE", False):
            with pytest.raises(ImportError, match="transformers package is required"):
                HuggingFaceReranker({"model": "test"})
