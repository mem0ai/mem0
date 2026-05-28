"""Tests for shared spaCy model loader."""

import pytest


class TestGetModelName:
    """_get_model_name() 模型名解析测试（纯逻辑，不需要 spaCy）。

    _get_model_name() 在函数体内读取 os.environ，monkeypatch.setenv 直接生效。
    """

    def test_default_is_en_core_web_sm(self, monkeypatch):
        monkeypatch.delenv("MEM0_SPACY_MODEL", raising=False)

        from mem0.utils.spacy_models import _get_model_name

        assert _get_model_name() == "en_core_web_sm"

    def test_language_code_zh_maps_to_zh_core_web_sm(self, monkeypatch):
        monkeypatch.setenv("MEM0_SPACY_MODEL", "zh")

        from mem0.utils.spacy_models import _get_model_name

        assert _get_model_name() == "zh_core_web_sm"

    def test_full_model_name_passthrough(self, monkeypatch):
        monkeypatch.setenv("MEM0_SPACY_MODEL", "ja_core_news_sm")

        from mem0.utils.spacy_models import _get_model_name

        assert _get_model_name() == "ja_core_news_sm"

    def test_unknown_language_code_passthrough(self, monkeypatch):
        monkeypatch.setenv("MEM0_SPACY_MODEL", "xx")

        from mem0.utils.spacy_models import _get_model_name

        assert _get_model_name() == "xx"


class TestSpacyModelCache:
    """get_nlp_full / get_nlp_lemma 缓存行为测试（需要 spaCy en_core_web_sm）。"""

    @pytest.fixture(autouse=True)
    def _ensure_spacy_and_default_env(self, monkeypatch):
        monkeypatch.delenv("MEM0_SPACY_MODEL", raising=False)
        try:
            import spacy
            spacy.load("en_core_web_sm")
        except Exception:
            pytest.skip("spaCy en_core_web_sm model not available")

    def test_get_nlp_full_returns_model(self):
        from mem0.utils.spacy_models import get_nlp_full

        assert get_nlp_full() is not None

    def test_get_nlp_lemma_returns_model(self):
        from mem0.utils.spacy_models import get_nlp_lemma

        assert get_nlp_lemma() is not None

    def test_same_instance_on_repeated_calls(self):
        from mem0.utils.spacy_models import get_nlp_full

        nlp1 = get_nlp_full()
        nlp2 = get_nlp_full()
        assert nlp1 is nlp2

    def test_full_and_lemma_are_different_models(self):
        from mem0.utils.spacy_models import get_nlp_full, get_nlp_lemma

        nlp_full = get_nlp_full()
        nlp_lemma = get_nlp_lemma()
        # lemma 模型禁用了 NER 和 parser，是不同的管道配置
        assert nlp_full is not nlp_lemma


class TestSpacyModelFailure:
    """无效模型降级测试（不需要 spaCy 模型）。"""

    def test_invalid_model_returns_none(self, monkeypatch):
        monkeypatch.setenv("MEM0_SPACY_MODEL", "nonexistent_model_xyz")

        from mem0.utils.spacy_models import get_nlp_full

        result = get_nlp_full()
        # 模型加载失败时应返回 None，不抛异常
        assert result is None
