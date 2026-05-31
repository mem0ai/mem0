from mem0.configs.rerankers.base import BaseRerankerConfig
from mem0.configs.rerankers.llm import LLMRerankerConfig
from mem0.reranker.llm_reranker import LLMReranker


class TestLLMRerankerConfig:
    def test_default_config(self):
        config = LLMRerankerConfig()
        assert config.model == "gpt-4o-mini"
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
