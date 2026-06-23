import pytest


@pytest.fixture(scope="session")
def ensure_spacy():
    """Skip a test when the English spaCy model is not available."""
    try:
        import spacy

        spacy.load("en_core_web_sm")
    except Exception:
        pytest.skip("spaCy en_core_web_sm model not available")


@pytest.mark.usefixtures("ensure_spacy")
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


class TestMultilingualBm25Fallback:
    def test_non_latin_inputs_do_not_touch_spacy(self, monkeypatch):
        from mem0.utils import spacy_models
        from mem0.utils.lemmatization import lemmatize_for_bm25

        def fail_if_called():
            raise AssertionError("spaCy should not be loaded for non-Latin text")

        monkeypatch.setattr(spacy_models, "get_nlp_lemma", fail_if_called)

        chinese_tokens = lemmatize_for_bm25("我喜欢喝榛子拿铁和年糕汤").split()
        thai_tokens = lemmatize_for_bm25("ฉันชอบดื่มกาแฟในตอนเช้า").split()
        mixed_tokens = lemmatize_for_bm25("员工 EMP-123 使用 sku_77").split()

        assert "榛子" in chinese_tokens
        assert "拿铁" in chinese_tokens
        assert len(thai_tokens) > 3
        assert "emp-123" in mixed_tokens
        assert "emp" in mixed_tokens
        assert "123" in mixed_tokens
        assert "sku_77" in mixed_tokens

    def test_chinese_memory_and_query_have_overlap(self):
        from mem0.utils.lemmatization import lemmatize_for_bm25

        stored = set(lemmatize_for_bm25("我喜欢喝榛子拿铁和年糕汤").split())
        query = set(lemmatize_for_bm25("榛子拿铁").split())

        assert "榛子" in stored
        assert "拿铁" in stored
        assert stored & query

    def test_thai_does_not_become_empty(self):
        from mem0.utils.lemmatization import lemmatize_for_bm25

        result = lemmatize_for_bm25("ฉันชอบดื่มกาแฟในตอนเช้า")

        assert result
        assert len(result.split()) > 3

    def test_mixed_identifier_is_preserved_for_exact_match(self):
        from mem0.utils.lemmatization import lemmatize_for_bm25

        tokens = lemmatize_for_bm25("员工 EMP-123 使用 sku_77").split()

        assert "emp-123" in tokens
        assert "emp" in tokens
        assert "123" in tokens
        assert "sku_77" in tokens

    def test_latin_text_falls_back_when_spacy_unavailable(self, monkeypatch):
        from mem0.utils import spacy_models
        from mem0.utils.lemmatization import lemmatize_for_bm25

        monkeypatch.setattr(spacy_models, "get_nlp_lemma", lambda: None)

        tokens = lemmatize_for_bm25("EMP-123 sku_77").split()

        assert "emp-123" in tokens
        assert "emp" in tokens
        assert "123" in tokens
        assert "sku_77" in tokens
        assert "sku" in tokens
        assert "77" in tokens

    def test_spacy_path_falls_back_when_all_tokens_are_discarded(self, monkeypatch):
        from mem0.utils import spacy_models
        from mem0.utils.lemmatization import lemmatize_for_bm25

        class FakeToken:
            def __init__(self, text, lemma, *, is_punct=False, is_stop=False):
                self.text = text
                self.lemma_ = lemma
                self.is_punct = is_punct
                self.is_stop = is_stop

        def fake_nlp(text):
            return [
                FakeToken("!", "!", is_punct=True),
                FakeToken(text, text, is_stop=True),
            ]

        monkeypatch.setattr(spacy_models, "get_nlp_lemma", lambda: fake_nlp)

        tokens = lemmatize_for_bm25("EMP-123 sku_77").split()

        assert "emp-123" in tokens
        assert "emp" in tokens
        assert "123" in tokens
        assert "sku_77" in tokens
        assert "sku" in tokens
        assert "77" in tokens

    def test_spacy_path_preserves_mixed_identifier_tokens(self, monkeypatch):
        from mem0.utils import spacy_models
        from mem0.utils.lemmatization import lemmatize_for_bm25

        class FakeToken:
            def __init__(self, text, lemma):
                self.text = text
                self.lemma_ = lemma
                self.is_punct = False
                self.is_stop = False

        def fake_nlp(text):
            assert text == "employee emp-123 sku_77"
            return [
                FakeToken("employee", "employee"),
                FakeToken("emp-123", "emp-123"),
                FakeToken("sku_77", "sku_77"),
            ]

        monkeypatch.setattr(spacy_models, "get_nlp_lemma", lambda: fake_nlp)

        tokens = lemmatize_for_bm25("Employee EMP-123 sku_77").split()

        assert "employee" in tokens
        assert "emp-123" in tokens
        assert "emp" in tokens
        assert "123" in tokens
        assert "sku_77" in tokens
        assert "sku" in tokens
        assert "77" in tokens

    def test_spacy_path_normalizes_fullwidth_ascii_tokens(self, monkeypatch):
        from mem0.utils import spacy_models
        from mem0.utils.lemmatization import lemmatize_for_bm25

        class FakeToken:
            def __init__(self, text):
                self.text = text
                self.lemma_ = text
                self.is_punct = False
                self.is_stop = False

        def fake_nlp(text):
            return [FakeToken(part) for part in text.split()]

        monkeypatch.setattr(spacy_models, "get_nlp_lemma", lambda: fake_nlp)

        fullwidth = set(lemmatize_for_bm25("ＡＢＣ １２３").split())
        ascii_tokens = set(lemmatize_for_bm25("ABC 123").split())

        assert {"abc", "123"} <= fullwidth
        assert fullwidth & ascii_tokens
