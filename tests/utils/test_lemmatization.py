import re

import pytest


@pytest.fixture
def _ensure_spacy():
    """Skip tests if spaCy model is not available."""
    try:
        import spacy

        spacy.load("en_core_web_sm")
    except Exception:
        pytest.skip("spaCy en_core_web_sm model not available")


class _FakeToken:
    def __init__(self, text, lemma):
        self.text = text
        self.lemma_ = lemma
        self.is_punct = False
        self.is_stop = text in {"a", "an", "are", "in", "is", "the"}


class _FakeEnglishNlp:
    """Small deterministic stand-in for the English spaCy pipeline."""

    _LEMMAS = {
        "employees": "employee",
        "manages": "manage",
    }

    def __call__(self, text):
        words = re.findall(r"[^\W_]+", text.lower())
        return [_FakeToken(word, self._LEMMAS.get(word, word)) for word in words]


@pytest.fixture
def fake_english_nlp(monkeypatch):
    monkeypatch.setattr("mem0.utils.spacy_models.get_nlp_lemma", lambda: _FakeEnglishNlp())


@pytest.mark.usefixtures("_ensure_spacy")
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


@pytest.mark.usefixtures("fake_english_nlp")
class TestMixedScriptLemmatization:
    def test_han_bigrams_overlap_between_memory_and_query(self):
        from mem0.utils.lemmatization import lemmatize_for_bm25

        memory_tokens = set(lemmatize_for_bm25("用户喜欢北京烤鸭").split())
        query_tokens = set(lemmatize_for_bm25("北京烤鸭").split())

        assert {"北京", "京烤", "烤鸭"} <= memory_tokens & query_tokens

    def test_mixed_text_routes_latin_and_han_spans_separately(self):
        from mem0.utils.lemmatization import lemmatize_for_bm25

        tokens = lemmatize_for_bm25("Alice喜欢北京烤鸭employees").split()

        assert "alice" in tokens
        assert "employee" in tokens
        assert {"喜欢", "北京", "烤鸭"} <= set(tokens)

    def test_identifier_is_preserved_as_one_exact_token(self):
        from mem0.utils.lemmatization import lemmatize_for_bm25

        tokens = lemmatize_for_bm25("张伟的员工编号是 CN-A10293").split()

        assert "cn-a10293" in tokens
        assert "cn" not in tokens
        assert "a10293" not in tokens

    def test_plain_hyphenated_word_is_not_treated_as_identifier(self):
        from mem0.utils.lemmatization import lemmatize_for_bm25

        tokens = lemmatize_for_bm25("state-of-the-art").split()

        assert "state-of-the-art" not in tokens
        assert {"state", "art"} <= set(tokens)

    def test_fullwidth_identifier_normalizes_to_ascii(self):
        from mem0.utils.lemmatization import lemmatize_for_bm25

        fullwidth = lemmatize_for_bm25("ＣＮ－Ａ１０２９３")
        ascii_text = lemmatize_for_bm25("CN-A10293")

        assert fullwidth == ascii_text == "cn-a10293"

    def test_accented_latin_text_is_not_routed_as_han(self):
        from mem0.utils.lemmatization import lemmatize_for_bm25

        assert lemmatize_for_bm25("café München") == "café münchen"

    def test_english_lemmatization_does_not_regress(self):
        from mem0.utils.lemmatization import lemmatize_for_bm25

        assert lemmatize_for_bm25("Alice manages employees") == "alice manage employee"

    def test_falls_back_without_spacy_for_mixed_text(self, monkeypatch):
        from mem0.utils.lemmatization import lemmatize_for_bm25

        monkeypatch.setattr("mem0.utils.spacy_models.get_nlp_lemma", lambda: None)

        tokens = lemmatize_for_bm25("Alice喜欢北京烤鸭 CN-A10293").split()
        assert {"alice", "喜欢", "北京", "烤鸭", "cn-a10293"} <= set(tokens)

    def test_pure_han_text_does_not_load_spacy(self, monkeypatch):
        from mem0.utils.lemmatization import lemmatize_for_bm25

        def fail_if_called():
            pytest.fail("pure Han text should not load spaCy")

        monkeypatch.setattr("mem0.utils.spacy_models.get_nlp_lemma", fail_if_called)

        assert lemmatize_for_bm25("北京烤鸭") == "北京 京烤 烤鸭"
        assert lemmatize_for_bm25("癌") == "癌"
