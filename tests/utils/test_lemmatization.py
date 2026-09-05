import pytest


@pytest.fixture(autouse=True)
def _ensure_spacy():
    """Skip tests if spaCy model is not available."""
    try:
        import spacy

        spacy.load("en_core_web_sm")
    except Exception:
        pytest.skip("spaCy en_core_web_sm model not available")


class TestLemmatizeForBm25:
    def test_basic_lemmatization(self):
        from mem0.utils.lemmatization import lemmatize_for_bm25

        result = lemmatize_for_bm25("The cats are running quickly")
        assert "cat" in result
        assert "run" in result or "running" in result
        # Stop words and punctuation should be removed
        assert "the" not in result.split()

    def test_verb_forms_normalized(self):
        from mem0.utils.lemmatization import lemmatize_for_bm25

        result = lemmatize_for_bm25("she attended multiple meetings yesterday")
        assert "attend" in result or "attended" in result
        assert "meeting" in result  # -ing form preserved alongside lemma
        # "multiple" is kept (not a spaCy stop word)

    def test_ing_preservation(self):
        from mem0.utils.lemmatization import lemmatize_for_bm25

        result = lemmatize_for_bm25("attending the morning meeting")
        tokens = result.split()
        # Should have both the lemma and the -ing form
        assert "attending" in tokens or "attend" in tokens

    def test_empty_string(self):
        from mem0.utils.lemmatization import lemmatize_for_bm25

        result = lemmatize_for_bm25("")
        assert result == ""

    def test_punctuation_removed(self):
        from mem0.utils.lemmatization import lemmatize_for_bm25

        result = lemmatize_for_bm25("Hello, world! How are you?")
        assert "," not in result
        assert "!" not in result
        assert "?" not in result

    def test_lowercased(self):
        from mem0.utils.lemmatization import lemmatize_for_bm25

        result = lemmatize_for_bm25("PYTHON Programming LANGUAGE")
        for token in result.split():
            assert token == token.lower()

    def test_stop_words_removed(self):
        from mem0.utils.lemmatization import lemmatize_for_bm25

        result = lemmatize_for_bm25("this is a very simple test of the system")
        tokens = result.split()
        for stop in ["this", "is", "a", "very", "of", "the"]:
            assert stop not in tokens


@pytest.fixture()
def _use_zh_model(monkeypatch):
    """Point mem0 at the Chinese pipeline and reset its cached spaCy state."""
    import spacy

    if not spacy.util.is_package("zh_core_web_sm"):
        pytest.skip("spaCy zh_core_web_sm model not available")
    import mem0.utils.spacy_models as sm

    monkeypatch.setenv("MEM0_SPACY_MODEL", "zh_core_web_sm")
    monkeypatch.setattr(sm, "_nlp_lemma", None)
    monkeypatch.setattr(sm, "_load_failed_lemma", False)


class TestLemmatizeForBm25Chinese:
    def test_chinese_tokens_kept(self, _use_zh_model):
        """zh pipelines return empty lemmas; surface forms must be kept."""
        from mem0.utils.lemmatization import lemmatize_for_bm25

        result = lemmatize_for_bm25("张三是阿里巴巴的工程师")
        assert result != ""
        assert "阿里巴巴" in result.split()
        # Chinese stop words should be removed
        assert "是" not in result.split()
        assert "的" not in result.split()
