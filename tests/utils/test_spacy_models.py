import sys
from types import ModuleType, SimpleNamespace

import pytest


@pytest.fixture(autouse=True)
def reset_spacy_model_cache():
    import mem0.utils.spacy_models as spacy_models

    spacy_models._reset_model_cache()
    yield
    spacy_models._reset_model_cache()


def install_fake_spacy(monkeypatch, *, is_package, load, download=None):
    spacy_module = ModuleType("spacy")
    cli_module = ModuleType("spacy.cli")

    spacy_module.__path__ = []
    spacy_module.util = SimpleNamespace(is_package=lambda name: is_package)
    spacy_module.load = load
    cli_module.download = download or (lambda name: None)
    spacy_module.cli = cli_module

    monkeypatch.setitem(sys.modules, "spacy", spacy_module)
    monkeypatch.setitem(sys.modules, "spacy.cli", cli_module)


def test_model_name_resolution_uses_specific_overrides(monkeypatch):
    import mem0.utils.spacy_models as spacy_models

    monkeypatch.setenv("MEM0_SPACY_MODEL", "xx_base")
    monkeypatch.setenv("MEM0_SPACY_ENTITY_MODEL", "zh_core_web_sm")
    monkeypatch.setenv("MEM0_SPACY_LEMMA_MODEL", "en_core_web_sm")

    assert spacy_models._get_model_name("full") == "zh_core_web_sm"
    assert spacy_models._get_model_name("lemma") == "en_core_web_sm"


def test_model_name_resolution_treats_blank_base_as_default(monkeypatch):
    import mem0.utils.spacy_models as spacy_models

    monkeypatch.setenv("MEM0_SPACY_MODEL", "   ")

    assert spacy_models._get_model_name("full") == "en_core_web_sm"
    assert spacy_models._get_model_name("lemma") == "en_core_web_sm"


def test_model_name_resolution_treats_blank_scoped_overrides_as_unset(monkeypatch):
    import mem0.utils.spacy_models as spacy_models

    monkeypatch.setenv("MEM0_SPACY_MODEL", "xx_base")
    monkeypatch.setenv("MEM0_SPACY_ENTITY_MODEL", "   ")
    monkeypatch.setenv("MEM0_SPACY_LEMMA_MODEL", "")

    assert spacy_models._get_model_name("full") == "xx_base"
    assert spacy_models._get_model_name("lemma") == "xx_base"


def test_model_name_resolution_rejects_unknown_kind():
    import mem0.utils.spacy_models as spacy_models

    with pytest.raises(ValueError, match="Unknown spaCy model kind"):
        spacy_models._get_model_name("bad")


def test_full_and_lemma_models_use_separate_cache_keys(monkeypatch):
    import mem0.utils.spacy_models as spacy_models

    loaded = []

    def fake_load(name, disable=None):
        loaded.append((name, tuple(disable or ())))
        return {"name": name, "disable": tuple(disable or ())}

    install_fake_spacy(monkeypatch, is_package=True, load=fake_load)
    monkeypatch.setenv("MEM0_SPACY_ENTITY_MODEL", "zh_core_web_sm")
    monkeypatch.setenv("MEM0_SPACY_LEMMA_MODEL", "en_core_web_sm")

    full = spacy_models.get_nlp_full()
    lemma = spacy_models.get_nlp_lemma()

    assert full == {"name": "zh_core_web_sm", "disable": ()}
    assert lemma == {"name": "en_core_web_sm", "disable": ("ner", "parser")}
    assert loaded == [("zh_core_web_sm", ()), ("en_core_web_sm", ("ner", "parser"))]


def test_custom_missing_model_logs_warning_and_returns_none(monkeypatch, caplog):
    import logging

    import mem0.utils.spacy_models as spacy_models

    def fail_load(name, disable=None):
        raise OSError(f"missing {name}")

    downloads = []

    install_fake_spacy(
        monkeypatch,
        is_package=False,
        load=fail_load,
        download=lambda name: downloads.append(name),
    )
    monkeypatch.setenv("MEM0_SPACY_ENTITY_MODEL", "zh_core_web_sm")

    with caplog.at_level(logging.WARNING, logger="mem0.utils.spacy_models"):
        assert spacy_models.get_nlp_full() is None

    assert downloads == []
    assert any("zh_core_web_sm" in record.message for record in caplog.records)
    assert any("python -m spacy download zh_core_web_sm" in record.message for record in caplog.records)


def test_default_missing_model_attempts_auto_download(monkeypatch):
    import mem0.utils.spacy_models as spacy_models

    downloads = []
    loaded = []

    def fake_load(name, disable=None):
        loaded.append((name, tuple(disable or ())))
        return {"name": name, "disable": tuple(disable or ())}

    install_fake_spacy(
        monkeypatch,
        is_package=False,
        load=fake_load,
        download=lambda name: downloads.append(name),
    )

    assert spacy_models.get_nlp_full() == {"name": "en_core_web_sm", "disable": ()}
    assert downloads == ["en_core_web_sm"]
    assert loaded == [("en_core_web_sm", ())]


def test_failed_model_load_is_cached_until_reset(monkeypatch):
    import mem0.utils.spacy_models as spacy_models

    calls = []
    should_fail = True

    def fake_load(name, disable=None):
        calls.append((name, tuple(disable or ())))
        if should_fail:
            raise OSError(f"missing {name}")
        return {"name": name, "disable": tuple(disable or ())}

    install_fake_spacy(monkeypatch, is_package=True, load=fake_load)
    monkeypatch.setenv("MEM0_SPACY_ENTITY_MODEL", "zh_core_web_sm")

    assert spacy_models.get_nlp_full() is None
    assert spacy_models.get_nlp_full() is None
    assert calls == [("zh_core_web_sm", ())]

    should_fail = False
    spacy_models._reset_model_cache()

    assert spacy_models.get_nlp_full() == {"name": "zh_core_web_sm", "disable": ()}
    assert calls == [("zh_core_web_sm", ()), ("zh_core_web_sm", ())]
