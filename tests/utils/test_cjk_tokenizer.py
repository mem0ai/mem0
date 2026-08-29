"""Tests for the pure-Python CJK tokenizer used by BM25 keyword matching."""

import pytest


class TestCjkTokenizer:
    def test_chinese_sentence_segmented(self):
        from mem0.utils.cjk_tokenizer import tokenize

        result = tokenize("我们最近配置的 rerank 精排是什么模型")
        # Latin word kept as exact token
        assert "rerank" in result
        # CJK bigrams present
        assert "最近" in result
        assert "配置" in result
        assert "模型" in result
        # Single-char stopwords dropped from document side
        assert "的" not in result
        assert "是" not in result

    def test_query_mode_bigrams_only(self):
        from mem0.utils.cjk_tokenizer import tokenize

        result = tokenize("混合检索", query_mode=True)
        # bigrams only — no unigrams
        assert "混合" in result
        assert "合检" in result
        assert "检索" in result
        assert "混" not in result
        assert "检" not in result

    def test_single_char_chunk_falls_back_to_unigram(self):
        from mem0.utils.cjk_tokenizer import tokenize

        result = tokenize("生日", query_mode=True)
        assert "生日" in result

    def test_latin_identifiers_kept_exact(self):
        from mem0.utils.cjk_tokenizer import tokenize

        result = tokenize("9router 的 memobase-use 映射 GOALS.md.")
        assert "9router" in result
        assert "memobase-use" in result
        assert "goals.md" in result  # trailing period stripped

    def test_empty_string(self):
        from mem0.utils.cjk_tokenizer import tokenize

        assert tokenize("") == []
        assert tokenize("", query_mode=True) == []

    def test_pure_latin_no_cjk(self):
        from mem0.utils.cjk_tokenizer import tokenize

        result = tokenize("The cats are running quickly")
        assert "cats" in result
        assert "running" in result


class TestLemmatizeForBm25Cjk:
    def test_cjk_routed_to_tokenizer(self):
        from mem0.utils.lemmatization import lemmatize_for_bm25

        result = lemmatize_for_bm25("我们最近配置的 rerank 精排是什么模型")
        # Space-joined tokens, CJK segmented
        assert "rerank" in result.split()
        assert "最近" in result.split()
        assert "模型" in result.split()

    def test_english_path_unchanged(self):
        from mem0.utils.lemmatization import lemmatize_for_bm25

        result = lemmatize_for_bm25("The cats are running quickly")
        # English path still works (spaCy or fallback)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_mixed_cjk_latin(self):
        from mem0.utils.lemmatization import lemmatize_for_bm25

        result = lemmatize_for_bm25("hybrid_retriever.py 里 RRF 的 k 是多少")
        assert "hybrid_retriever.py" in result.split()
        assert "rrf" in result.split()
