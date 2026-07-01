import pytest


@pytest.fixture(autouse=True)
def _ensure_spacy():
    """Skip tests if spaCy model is not available."""
    try:
        import spacy

        spacy.load("en_core_web_sm")
    except Exception:
        pytest.skip("spaCy en_core_web_sm model not available")


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

    def test_empty_input(self):
        from mem0.utils.entity_extraction import extract_entities_batch

        assert extract_entities_batch([]) == []

    def test_consistency_with_single(self):
        from mem0.utils.entity_extraction import extract_entities, extract_entities_batch

        text = "John Smith works at Google headquarters"
        single = extract_entities(text)
        batch = extract_entities_batch([text])
        assert len(batch) == 1
        # Both should extract the same entities
        assert set(t for _, t in single) == set(t for _, t in batch[0])


class _NoNounChunksDoc:
    """Wrap a real spaCy Doc but make ``noun_chunks`` raise NotImplementedError.

    spaCy does not implement the noun_chunks syntax iterator for every language
    (zh/ja raise NotImplementedError [E894]). This reproduces that on a real
    English Doc so the rest of the extraction pipeline runs against real tokens.
    """

    def __init__(self, doc):
        self._doc = doc

    @property
    def noun_chunks(self):
        raise NotImplementedError(
            "[E894] The 'noun_chunks' syntax iterator is not implemented for language 'zh'."
        )

    def __iter__(self):
        return iter(self._doc)

    def __getattr__(self, name):
        return getattr(self._doc, name)


class TestUnsupportedLanguageNounChunks:
    def test_noun_chunks_not_implemented_does_not_abort_extraction(self):
        """A language without noun_chunks (#5285) must not crash extraction.

        Guards #5550: _add_topic_phrase_candidates iterated doc.noun_chunks
        directly, so a NotImplementedError aborted ALL entity extraction.
        """
        import spacy

        from mem0.utils.entity_extraction import _EntityCandidate, _add_topic_phrase_candidates

        nlp = spacy.load("en_core_web_sm")
        real_doc = nlp("John Smith works at Google on machine learning projects")
        wrapped = _NoNounChunksDoc(real_doc)

        candidates: list[_EntityCandidate] = []
        # Must not raise even though noun_chunks is unavailable.
        _add_topic_phrase_candidates(wrapped, candidates)
