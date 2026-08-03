"""Tests for the shared spaCy model loader.

The model name is configurable via the MEM0_SPACY_MODEL env var so that
non-English pipelines (zh_core_web_sm, ja_core_news_sm, ...) can be used.
These tests mock spacy.load / download so no real model is required.
"""

import pytest

spacy = pytest.importorskip("spacy")


class TestModelName:
    def test_default_model_name(self):
        from mem0.utils import spacy_models

        assert spacy_models._get_model_name() == "en_core_web_sm"

    def test_env_override(self, monkeypatch):
        from mem0.utils import spacy_models

        monkeypatch.setenv("MEM0_SPACY_MODEL", "zh_core_web_sm")
        assert spacy_models._get_model_name() == "zh_core_web_sm"


class TestGetNlpFull:
    def test_loads_default_model(self, monkeypatch):
        from mem0.utils import spacy_models

        monkeypatch.delenv("MEM0_SPACY_MODEL", raising=False)
        monkeypatch.setattr(spacy.util, "is_package", lambda name: True)
        monkeypatch.setattr(spacy_models, "_nlp_full", None)
        monkeypatch.setattr(spacy_models, "_load_failed_full", False)
        loaded = {}

        def fake_load(name, **kwargs):
            loaded["name"] = name
            return object()

        monkeypatch.setattr(spacy, "load", fake_load)

        spacy_models.get_nlp_full()

        assert loaded["name"] == "en_core_web_sm"

    def test_loads_env_model(self, monkeypatch):
        from mem0.utils import spacy_models

        monkeypatch.setenv("MEM0_SPACY_MODEL", "ja_core_news_sm")
        monkeypatch.setattr(spacy.util, "is_package", lambda name: True)
        monkeypatch.setattr(spacy_models, "_nlp_full", None)
        monkeypatch.setattr(spacy_models, "_load_failed_full", False)
        loaded = {}

        def fake_load(name, **kwargs):
            loaded["name"] = name
            return object()

        monkeypatch.setattr(spacy, "load", fake_load)

        spacy_models.get_nlp_full()

        assert loaded["name"] == "ja_core_news_sm"


class TestGetNlpLemma:
    def test_loads_env_model_with_disabled_pipes(self, monkeypatch):
        from mem0.utils import spacy_models

        monkeypatch.setenv("MEM0_SPACY_MODEL", "zh_core_web_sm")
        monkeypatch.setattr(spacy.util, "is_package", lambda name: True)
        monkeypatch.setattr(spacy_models, "_nlp_lemma", None)
        monkeypatch.setattr(spacy_models, "_load_failed_lemma", False)
        loaded = {}

        def fake_load(name, **kwargs):
            loaded["name"] = name
            loaded["kwargs"] = kwargs
            return object()

        monkeypatch.setattr(spacy, "load", fake_load)

        spacy_models.get_nlp_lemma()

        assert loaded["name"] == "zh_core_web_sm"
        assert loaded["kwargs"] == {"disable": ["ner", "parser"]}


class TestEnsureModelAvailable:
    def test_downloads_env_model_when_missing(self, monkeypatch):
        import spacy.cli

        from mem0.utils import spacy_models

        monkeypatch.setenv("MEM0_SPACY_MODEL", "de_core_news_sm")
        monkeypatch.setattr(spacy.util, "is_package", lambda name: False)
        downloaded = []
        monkeypatch.setattr(spacy.cli, "download", lambda name: downloaded.append(name))

        spacy_models._ensure_model_available()

        assert downloaded == ["de_core_news_sm"]
