import pytest

from mem0.reranker.llm_reranker import LLMReranker


class TestExtractScore:
    @pytest.fixture
    def reranker(self, mock_llm):
        return LLMReranker({"provider": "openai"})

    @pytest.mark.parametrize(
        "text,expected",
        [
            ("0.85", 0.85),
            ("0.0", 0.0),
            ("1.0", 1.0),
            ("The score is 0.72.", 0.72),
            ("Score: 0.9 out of 1.0", 0.9),
        ],
    )
    def test_valid_scores(self, reranker, text, expected):
        assert reranker._extract_score(text) == expected

    def test_no_score_returns_fallback(self, reranker):
        assert reranker._extract_score("no numbers here") == 0.5

    def test_clamps_to_1(self, reranker):
        assert reranker._extract_score("1.0") == 1.0


class TestRerank:
    def test_empty_documents(self, mock_llm):
        reranker = LLMReranker({"provider": "openai"})
        result = reranker.rerank("query", [])
        assert result == []

    def test_documents_sorted_by_score_descending(self, mock_llm):
        _, mock_llm_instance = mock_llm
        mock_llm_instance.generate_response.side_effect = ["0.3", "0.9", "0.6"]

        reranker = LLMReranker({"provider": "openai"})
        docs = [
            {"memory": "low relevance"},
            {"memory": "high relevance"},
            {"memory": "mid relevance"},
        ]

        result = reranker.rerank("test query", docs)

        assert len(result) == 3
        assert result[0]["rerank_score"] == 0.9
        assert result[1]["rerank_score"] == 0.6
        assert result[2]["rerank_score"] == 0.3

    def test_top_k_limits_results(self, mock_llm):
        _, mock_llm_instance = mock_llm
        mock_llm_instance.generate_response.side_effect = ["0.9", "0.5", "0.1"]

        reranker = LLMReranker({"provider": "openai"})
        docs = [{"memory": f"doc{i}"} for i in range(3)]

        result = reranker.rerank("query", docs, top_k=2)
        assert len(result) == 2

    def test_config_top_k_used_when_arg_not_provided(self, mock_llm):
        _, mock_llm_instance = mock_llm
        mock_llm_instance.generate_response.side_effect = ["0.9", "0.5", "0.1"]

        reranker = LLMReranker({"provider": "openai", "top_k": 1})
        docs = [{"memory": f"doc{i}"} for i in range(3)]

        result = reranker.rerank("query", docs)
        assert len(result) == 1

    def test_text_field_extraction(self, mock_llm):
        _, mock_llm_instance = mock_llm
        mock_llm_instance.generate_response.return_value = "0.8"

        reranker = LLMReranker({"provider": "openai"})
        reranker.rerank("query", [{"text": "some text"}])

        user_msg = mock_llm_instance.generate_response.call_args[1]["messages"][1]["content"]
        assert "some text" in user_msg

    def test_content_field_extraction(self, mock_llm):
        _, mock_llm_instance = mock_llm
        mock_llm_instance.generate_response.return_value = "0.8"

        reranker = LLMReranker({"provider": "openai"})
        reranker.rerank("query", [{"content": "some content"}])

        user_msg = mock_llm_instance.generate_response.call_args[1]["messages"][1]["content"]
        assert "some content" in user_msg

    def test_fallback_score_on_llm_error(self, mock_llm):
        _, mock_llm_instance = mock_llm
        mock_llm_instance.generate_response.side_effect = RuntimeError("API error")

        reranker = LLMReranker({"provider": "openai"})
        result = reranker.rerank("query", [{"memory": "doc"}])

        assert len(result) == 1
        assert result[0]["rerank_score"] == 0.5

    def test_custom_scoring_prompt(self, mock_llm):
        _, mock_llm_instance = mock_llm
        mock_llm_instance.generate_response.return_value = "0.7"

        custom_prompt = "Rate relevance on a scale of 0.0 to 1.0."
        reranker = LLMReranker({"provider": "openai", "scoring_prompt": custom_prompt})
        reranker.rerank("my query", [{"memory": "my doc"}])

        messages = mock_llm_instance.generate_response.call_args[1]["messages"]
        assert messages[0]["content"] == custom_prompt
        assert "my query" in messages[1]["content"]
        assert "my doc" in messages[1]["content"]

    def test_original_doc_not_mutated(self, mock_llm):
        _, mock_llm_instance = mock_llm
        mock_llm_instance.generate_response.return_value = "0.8"

        reranker = LLMReranker({"provider": "openai"})
        original_doc = {"memory": "test", "id": "123"}
        result = reranker.rerank("query", [original_doc])

        assert "rerank_score" not in original_doc
        assert "rerank_score" in result[0]
