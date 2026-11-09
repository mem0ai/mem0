from mem0.configs.rerankers.base import BaseRerankerConfig
from mem0.configs.rerankers.llm import LLMRerankerConfig
from mem0.reranker.llm_reranker import LLMReranker


class TestLLMRerankerConfig:
    def test_default_config(self):
        config = LLMRerankerConfig()
        assert config.model == "gpt-5-mini"
        assert config.provider == "openai"
        assert config.temperature == 0.0
        assert config.max_tokens == 100
        assert config.llm is None
        assert config.scoring_prompt is None
        assert config.top_k is None

    def test_nested_llm_field_accepted(self):
        config = LLMRerankerConfig(
            llm={"provider": "ollama", "config": {"ollama_base_url": "http://localhost:11434"}}
        )
        assert config.llm["provider"] == "ollama"
        assert config.llm["config"]["ollama_base_url"] == "http://localhost:11434"


class TestLLMRerankerInit:
    def test_init_with_dict_config(self, mock_llm):
        mock_factory, _ = mock_llm
        reranker = LLMReranker({"provider": "openai", "model": "gpt-4o", "api_key": "sk-test"})

        assert reranker.config.provider == "openai"
        assert reranker.config.model == "gpt-4o"
        mock_factory.create.assert_called_once_with(
            "openai",
            {"model": "gpt-4o", "temperature": 0.0, "max_tokens": 100, "api_key": "sk-test"},
        )

    def test_init_with_llm_reranker_config(self, mock_llm):
        mock_factory, _ = mock_llm
        config = LLMRerankerConfig(provider="anthropic", model="claude-3-haiku", api_key="sk-ant")
        reranker = LLMReranker(config)

        assert reranker.config.provider == "anthropic"
        mock_factory.create.assert_called_once_with(
            "anthropic",
            {"model": "claude-3-haiku", "temperature": 0.0, "max_tokens": 100, "api_key": "sk-ant"},
        )

    def test_init_converts_base_reranker_config(self, mock_llm):
        mock_factory, _ = mock_llm
        base_config = BaseRerankerConfig(provider="openai", model="gpt-4o-mini")
        reranker = LLMReranker(base_config)

        assert isinstance(reranker.config, LLMRerankerConfig)
        assert reranker.config.temperature == 0.0
        assert reranker.config.max_tokens == 100

    def test_init_without_api_key(self, mock_llm):
        mock_factory, _ = mock_llm
        LLMReranker({"provider": "openai", "model": "gpt-4o-mini"})

        call_args = mock_factory.create.call_args
        llm_config = call_args[0][1]
        assert "api_key" not in llm_config


class TestLLMRerankerExtractScore:
    """_extract_score must parse full numeric tokens: scientific notation and
    leading-dot decimals used to clamp to 1.0 from a bare mantissa match
    (issue #7880), reversing search ranking."""

    def _make_reranker(self, mock_llm):
        mock_factory, llm_instance = mock_llm
        reranker = LLMReranker({"provider": "openai", "model": "gpt-4o", "api_key": "sk-test"})
        return reranker, llm_instance

    def test_scientific_notation_parsed_correctly(self, mock_llm):
        reranker, llm_instance = self._make_reranker(mock_llm)
        llm_instance.generate_response.side_effect = ["5e-2", "0.9"]
        docs = [
            {"id": "irrelevant", "memory": "taxes"},
            {"id": "relevant", "memory": "dog named Max"},
        ]
        result = reranker.rerank("query", docs, top_k=1)
        assert result[0]["id"] == "relevant"

    def test_scientific_notation_score_values(self, mock_llm):
        reranker, llm_instance = self._make_reranker(mock_llm)
        for response, expected in [("5e-2", 0.05), ("9.5e-1", 0.95), (".05", 0.05), ("9", 1.0), ("2.0", 1.0)]:
            llm_instance.generate_response.return_value = response
            assert reranker._extract_score(response) == expected, f"{response!r} -> {reranker._extract_score(response)}"

    def test_leading_dot_decimal_parsed(self, mock_llm):
        reranker, llm_instance = self._make_reranker(mock_llm)
        assert reranker._extract_score(".05") == 0.05

    def test_negative_score_clamped_to_zero(self, mock_llm):
        reranker, llm_instance = self._make_reranker(mock_llm)
        assert reranker._extract_score("-0.5") == 0.0

    def test_score_embedded_in_text(self, mock_llm):
        reranker, llm_instance = self._make_reranker(mock_llm)
        assert reranker._extract_score("score: 0.85") == 0.85

    def test_no_match_falls_back_to_neutral(self, mock_llm):
        reranker, llm_instance = self._make_reranker(mock_llm)
        assert reranker._extract_score("no numbers here") == 0.5
