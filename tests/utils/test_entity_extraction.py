import pytest


@pytest.fixture()
def ensure_spacy():
    """Skip a test when the English spaCy model is not available."""
    try:
        import spacy

        spacy.load("en_core_web_sm")
    except Exception:
        pytest.skip("spaCy en_core_web_sm model not available")


@pytest.mark.usefixtures("ensure_spacy")
class TestExtractEntities:
    def test_proper_nouns(self):
        from mem0.utils.entity_extraction import extract_entities

        entities = extract_entities("John Smith works at Google on machine learning projects")
        entity_texts = [e[1] for e in entities]
        # Should extract proper nouns
        found_proper = any("John" in t or "Google" in t for t in entity_texts)
        assert found_proper, f"Expected proper nouns, got {entities}"

    def test_quoted_text(self):
        from mem0.utils.entity_extraction import extract_entities

        entities = extract_entities('She is reading "The Great Gatsby" this week')
        entity_texts = [e[1] for e in entities]
        assert any("Great Gatsby" in t for t in entity_texts), f"Expected quoted text, got {entities}"

    def test_compound_nouns(self):
        from mem0.utils.entity_extraction import extract_entities

        entities = extract_entities("The machine learning engineer built a neural network")
        entity_texts = [e[1].lower() for e in entities]
        has_compound = any("machine" in t and "learning" in t for t in entity_texts) or any(
            "neural" in t and "network" in t for t in entity_texts
        )
        assert has_compound, f"Expected compound nouns, got {entities}"

    def test_empty_string(self):
        from mem0.utils.entity_extraction import extract_entities

        entities = extract_entities("")
        assert entities == []

    def test_no_entities(self):
        from mem0.utils.entity_extraction import extract_entities

        entities = extract_entities("I like things and stuff")
        # Generic words should be filtered out
        entity_texts = [e[1].lower() for e in entities]
        assert "things" not in entity_texts
        assert "stuff" not in entity_texts

    def test_deduplication(self):
        from mem0.utils.entity_extraction import extract_entities

        entities = extract_entities("Google is great. I love working at Google.")
        google_count = sum(1 for _, t in entities if "Google" in t)
        assert google_count <= 1, f"Expected dedup, got {entities}"

    def test_substring_dedup_respects_word_boundaries(self):
        from mem0.utils.entity_extraction import extract_entities

        # "Sam" is a mid-word substring of "Samsung", not a separate token, so it
        # must not be dropped as a substring of the longer entity.
        entities = extract_entities("At Samsung, Sam leads design.")
        entity_texts = [e[1] for e in entities]
        assert "Sam" in entity_texts, f"Expected 'Sam' to survive alongside 'Samsung', got {entities}"
        assert any("Samsung" in t for t in entity_texts), f"Expected 'Samsung', got {entities}"

    def test_returns_tuples(self):
        from mem0.utils.entity_extraction import extract_entities

        entities = extract_entities("John Smith lives in New York City")
        for entity in entities:
            assert isinstance(entity, tuple)
            assert len(entity) == 2
            assert entity[0] in ("PROPER", "QUOTED", "TOPIC", "IDENTIFIER")
            assert isinstance(entity[1], str)

    def test_handles_names_lists_and_identifiers(self):
        from mem0.utils.entity_extraction import extract_entities

        text = (
            "User reported top inbound integration pages: OpenClaw 25,443, "
            "Claude Code 8,916, Codex 2,573, Dify 656. "
            "User compared Cartesia and Deepgram. "
            "The email field for Mem0 lives at person.properties.email. "
            "The qwen endpoint uses person.properties.email. "
            "Johnson & Johnson was mentioned. "
            "Glasses around my window. "
            "On 2026-05-27 there were 90 days of stats."
        )

        entities = extract_entities(text)
        entity_texts = {entity_text for _, entity_text in entities}
        normalized = {entity_text.lower() for entity_text in entity_texts}

        assert {"OpenClaw", "Claude Code", "Codex", "Dify", "Cartesia", "Deepgram", "Mem0"}.issubset(entity_texts)
        assert "person.properties.email" in entity_texts
        assert "qwen endpoint" in entity_texts
        assert "Johnson & Johnson" in entity_texts
        assert "top" not in normalized
        assert "glasses" not in normalized
        assert "Cartesia and Deepgram" not in entity_texts
        assert "Claude Code 8,916" not in entity_texts
        assert not {"8,916", "2,573", "656", "2026-05-27", "90"}.intersection(entity_texts)


@pytest.mark.usefixtures("ensure_spacy")
class TestExtractEntitiesBatch:
    def test_batch_processing(self):
        from mem0.utils.entity_extraction import extract_entities_batch

        texts = [
            "John works at Google",
            "Mary lives in Paris",
            "The cat sat on the mat",
        ]
        results = extract_entities_batch(texts)
        assert len(results) == 3
        assert isinstance(results[0], list)
        assert isinstance(results[1], list)
        assert isinstance(results[2], list)

    def test_consistency_with_single(self):
        from mem0.utils.entity_extraction import extract_entities, extract_entities_batch

        text = "John Smith works at Google headquarters"
        single = extract_entities(text)
        batch = extract_entities_batch([text])
        assert len(batch) == 1
        # Both should extract the same entities
        assert set(t for _, t in single) == set(t for _, t in batch[0])


def test_batch_empty_input():
    from mem0.utils.entity_extraction import extract_entities_batch

    assert extract_entities_batch([]) == []


class FakeEnt:
    def __init__(self, text, label="PERSON", start=0):
        self.text = text
        self.label_ = label
        self._tokens = [FakeToken(start, text)]

    def __iter__(self):
        return iter(self._tokens)


class FakeToken:
    text = "x"
    text_with_ws = "x "
    lemma_ = "x"
    pos_ = "NOUN"
    dep_ = "ROOT"
    tag_ = "NN"
    is_sent_start = False
    is_stop = False

    def __init__(self, i=0, text="x"):
        self.i = i
        self.text = text
        self.text_with_ws = f"{text} "
        self.lemma_ = text.lower()
        self.head = self


class FakeDoc:
    def __init__(self, text="阿宁在苏州使用 EMP-123", ents=None, noun_chunks_error=None):
        self.text = text
        self.ents = [FakeEnt("阿宁", start=0), FakeEnt("苏州", start=1)] if ents is None else ents
        self._tokens = [FakeToken(idx, ent.text) for idx, ent in enumerate(self.ents)]
        self._noun_chunks_error = noun_chunks_error or NotImplementedError(
            "noun_chunks not implemented for this language"
        )

    def __iter__(self):
        return iter(self._tokens)

    @property
    def noun_chunks(self):
        raise self._noun_chunks_error


class FakeNlp:
    def __init__(self, docs):
        self.docs = docs

    def pipe(self, texts, batch_size=32):
        yield from self.docs


def test_extracts_spacy_doc_entities_as_proper_entities():
    from mem0.utils.entity_extraction import _extract_entities_from_doc

    entities = _extract_entities_from_doc(FakeDoc())

    assert ("PROPER", "阿宁") in entities
    assert ("PROPER", "苏州") in entities


def test_unsupported_noun_chunks_do_not_crash():
    from mem0.utils.entity_extraction import _extract_entities_from_doc

    entities = _extract_entities_from_doc(FakeDoc())

    assert isinstance(entities, list)


def test_value_error_noun_chunks_do_not_crash_and_keep_doc_entities():
    from mem0.utils.entity_extraction import _extract_entities_from_doc

    entities = _extract_entities_from_doc(
        FakeDoc(text="東京で働く", ents=[FakeEnt("東京")], noun_chunks_error=ValueError("unsupported parser"))
    )

    assert ("PROPER", "東京") in entities


def test_fallback_entities_work_without_spacy(monkeypatch):
    from mem0.utils import spacy_models
    from mem0.utils.entity_extraction import extract_entities

    monkeypatch.setattr(spacy_models, "get_nlp_full", lambda: None)

    entities = extract_entities('用户说 "年糕汤" 的员工编号是 EMP-123')

    assert ("QUOTED", "年糕汤") in entities
    assert ("IDENTIFIER", "EMP-123") in entities


def test_unicode_quote_fallback_entities_work_without_spacy(monkeypatch):
    from mem0.utils import spacy_models
    from mem0.utils.entity_extraction import extract_entities

    monkeypatch.setattr(spacy_models, "get_nlp_full", lambda: None)

    entities = extract_entities("用户说 “阿宁”，地点是「東京」，标题是『서울』，书名是《山海》")

    assert ("QUOTED", "阿宁") in entities
    assert ("QUOTED", "東京") in entities
    assert ("QUOTED", "서울") in entities
    assert ("QUOTED", "山海") in entities


def test_single_quote_fallback_entities_work_without_spacy(monkeypatch):
    from mem0.utils import spacy_models
    from mem0.utils.entity_extraction import extract_entities

    monkeypatch.setattr(spacy_models, "get_nlp_full", lambda: None)

    entities = extract_entities("用户说 '年糕汤' 的员工编号是 EMP-123")

    assert ("QUOTED", "年糕汤") in entities
    assert ("IDENTIFIER", "EMP-123") in entities


def test_code_like_substring_entities_are_not_pruned_without_spacy(monkeypatch):
    from mem0.utils import spacy_models
    from mem0.utils.entity_extraction import extract_entities

    monkeypatch.setattr(spacy_models, "get_nlp_full", lambda: None)

    entities = extract_entities("Use ABC-123 and ABC-123-def as distinct IDs")

    assert ("IDENTIFIER", "ABC-123") in entities
    assert ("IDENTIFIER", "ABC-123-def") in entities


def test_spacy_proper_entity_beats_regex_quoted_duplicate(monkeypatch):
    from mem0.utils import spacy_models
    from mem0.utils.entity_extraction import extract_entities

    monkeypatch.setattr(
        spacy_models,
        "get_nlp_full",
        lambda: lambda text: FakeDoc(text=text, ents=[FakeEnt("Apple", label="ORG")]),
    )

    entities = extract_entities('The note says "Apple" and Apple shipped the fix')

    assert ("PROPER", "Apple") in entities
    assert ("QUOTED", "Apple") not in entities


def test_code_regex_ignores_common_short_alphanumeric_words_without_spacy(monkeypatch):
    from mem0.utils import spacy_models
    from mem0.utils.entity_extraction import extract_entities

    monkeypatch.setattr(spacy_models, "get_nlp_full", lambda: None)

    entities = extract_entities("Ship ABC-123, not 4th, Python3, B2B, or G20. Keep AB12CD.")
    entity_texts = {text for _, text in entities}

    assert "ABC-123" in entity_texts
    assert "AB12CD" in entity_texts
    assert not {"4th", "Python3", "B2B", "G20"}.intersection(entity_texts)


def test_batch_preserves_length_when_pipe_returns_fewer_docs(monkeypatch):
    from mem0.utils import spacy_models
    from mem0.utils.entity_extraction import extract_entities_batch

    texts = ['用户说 "年糕汤"', "员工编号是 EMP-123"]
    monkeypatch.setattr(spacy_models, "get_nlp_full", lambda: FakeNlp([FakeDoc(text=texts[0], ents=[])]))

    results = extract_entities_batch(texts)

    assert len(results) == len(texts)
    assert ("QUOTED", "年糕汤") in results[0]
    assert ("IDENTIFIER", "EMP-123") in results[1]


def test_batch_preserves_length_when_pipe_returns_extra_docs(monkeypatch):
    from mem0.utils import spacy_models
    from mem0.utils.entity_extraction import extract_entities_batch

    texts = ["员工编号是 EMP-123"]
    monkeypatch.setattr(
        spacy_models,
        "get_nlp_full",
        lambda: FakeNlp([FakeDoc(text=texts[0], ents=[]), FakeDoc(text="额外 “서울”", ents=[FakeEnt("서울")])]),
    )

    results = extract_entities_batch(texts)

    assert len(results) == len(texts)
    assert ("IDENTIFIER", "EMP-123") in results[0]
    assert all(entity_text != "서울" for result in results for _, entity_text in result)


def test_no_spacy_batch_fallback_matches_single(monkeypatch):
    from mem0.utils import spacy_models
    from mem0.utils.entity_extraction import extract_entities, extract_entities_batch

    monkeypatch.setattr(spacy_models, "get_nlp_full", lambda: None)
    texts = ['用户说 "年糕汤"', "员工编号是 EMP-123", "Use ABC-123 and ABC-123-def as distinct IDs"]

    assert extract_entities_batch(texts) == [extract_entities(text) for text in texts]
