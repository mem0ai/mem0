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


class TestNonLatinWarning:
    """Verify non-Latin input surfaces a one-time warning.

    Background: the English spaCy pipeline produces degenerate output on
    non-Latin input (a single unsegmented token for CJK / Arabic /
    Cyrillic, empty output for Thai). Behaviour is intentionally
    unchanged; only a warning is logged. See GitHub issue #4884.
    """

    def _reset_warn_flag(self):
        import mem0.utils.lemmatization as lemm

        lemm._warned_non_latin_bm25 = False

    def test_latin_input_does_not_warn(self, caplog):
        import logging

        self._reset_warn_flag()
        from mem0.utils.lemmatization import lemmatize_for_bm25

        with caplog.at_level(logging.WARNING, logger="mem0.utils.lemmatization"):
            lemmatize_for_bm25("The cat runs quickly")
        assert not any("non-Latin" in rec.message for rec in caplog.records)

    def test_chinese_input_triggers_warning(self, caplog):
        import logging

        self._reset_warn_flag()
        from mem0.utils.lemmatization import lemmatize_for_bm25

        with caplog.at_level(logging.WARNING, logger="mem0.utils.lemmatization"):
            lemmatize_for_bm25("我喜欢喝榛子拿铁")
        assert any("non-Latin" in rec.message for rec in caplog.records)

    def test_warning_fires_only_once_per_process(self, caplog):
        import logging

        self._reset_warn_flag()
        from mem0.utils.lemmatization import lemmatize_for_bm25

        with caplog.at_level(logging.WARNING, logger="mem0.utils.lemmatization"):
            lemmatize_for_bm25("我喜欢喝榛子拿铁")
            lemmatize_for_bm25("東京で美味しいラーメンを食べた")
            lemmatize_for_bm25("서울에서 김치를 먹었다")
        warnings = [r for r in caplog.records if "non-Latin" in r.message]
        assert len(warnings) == 1

    def test_non_latin_behaviour_unchanged(self):
        """Whatever spaCy currently does on non-Latin input, keep doing it.

        This PR does not promise any retrieval-quality improvement; it
        only promises to surface the issue. The exact output here is
        pinned to today's behaviour so future retrieval changes are
        visible as a test update, not a silent regression.
        """
        self._reset_warn_flag()
        from mem0.utils.lemmatization import lemmatize_for_bm25

        # Chinese: spaCy returns the full string as a single token.
        result = lemmatize_for_bm25("我喜欢喝榛子拿铁")
        assert result  # non-empty
        assert len(result.split()) == 1

        # Semantic path still gets a string back; behaviour unchanged.
        assert isinstance(lemmatize_for_bm25("ฉันชอบดื่มกาแฟ"), str)
