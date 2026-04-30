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
        has_compound = any("machine" in t and "learning" in t for t in entity_texts) or \
                       any("neural" in t and "network" in t for t in entity_texts)
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

    def test_returns_tuples(self):
        from mem0.utils.entity_extraction import extract_entities

        entities = extract_entities("John Smith lives in New York City")
        for entity in entities:
            assert isinstance(entity, tuple)
            assert len(entity) == 2
            assert entity[0] in ("PROPER", "QUOTED", "COMPOUND", "NOUN")
            assert isinstance(entity[1], str)


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


class TestNonLatinWarning:
    """Entity extraction must warn (once) when the pipeline cannot help."""

    def _reset_warn_flag(self):
        import mem0.utils.entity_extraction as ee

        ee._warned_non_latin_entities = False

    def test_latin_input_does_not_warn(self, caplog):
        import logging

        self._reset_warn_flag()
        from mem0.utils.entity_extraction import extract_entities

        with caplog.at_level(logging.WARNING, logger="mem0.utils.entity_extraction"):
            extract_entities("John Smith works at Google")
        assert not any("non-Latin" in r.message for r in caplog.records)

    def test_chinese_input_warns_once(self, caplog):
        import logging

        self._reset_warn_flag()
        from mem0.utils.entity_extraction import extract_entities

        with caplog.at_level(logging.WARNING, logger="mem0.utils.entity_extraction"):
            extract_entities("阿宁住在苏州养了一只猫叫年糕")
            extract_entities("東京で美味しいラーメンを食べた")
        warnings = [r for r in caplog.records if "non-Latin" in r.message]
        assert len(warnings) == 1

    def test_batch_with_non_latin_warns_once(self, caplog):
        import logging

        self._reset_warn_flag()
        from mem0.utils.entity_extraction import extract_entities_batch

        with caplog.at_level(logging.WARNING, logger="mem0.utils.entity_extraction"):
            extract_entities_batch(
                ["John lives in Paris", "阿宁住在苏州", "東京で食べた"]
            )
        warnings = [r for r in caplog.records if "non-Latin" in r.message]
        assert len(warnings) == 1

    def test_non_latin_returns_empty_entities(self):
        """Behaviour pin: current pipeline returns [] for pure non-Latin."""
        self._reset_warn_flag()
        from mem0.utils.entity_extraction import extract_entities

        assert extract_entities("阿宁住在苏州") == []
        assert extract_entities("東京で食べた") == []
