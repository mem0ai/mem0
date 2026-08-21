class TestSpacyModelName:
    def test_default_is_en(self, monkeypatch):
        monkeypatch.delenv("MEM0_SPACY_MODEL", raising=False)
        from mem0.utils.spacy_models import _spacy_model_name

        assert _spacy_model_name() == "en_core_web_sm"

    def test_env_override(self, monkeypatch):
        monkeypatch.setenv("MEM0_SPACY_MODEL", "zh_core_web_sm")
        from mem0.utils.spacy_models import _spacy_model_name

        assert _spacy_model_name() == "zh_core_web_sm"

    def test_blank_env_falls_back_to_default(self, monkeypatch):
        monkeypatch.setenv("MEM0_SPACY_MODEL", "  ")
        from mem0.utils.spacy_models import _spacy_model_name

        assert _spacy_model_name() == "en_core_web_sm"
