from mem0.reranker.llm_reranker import LLMReranker


class TestNestedLLMConfig:
    def test_nested_llm_overrides_provider(self, mock_llm):
        mock_factory, _ = mock_llm
        LLMReranker({
            "provider": "openai",
            "model": "gpt-4o-mini",
            "llm": {
                "provider": "ollama",
                "config": {"model": "llama3", "ollama_base_url": "http://localhost:11434"},
            },
        })

        call_args = mock_factory.create.call_args
        assert call_args[0][0] == "ollama"

    def test_nested_llm_passes_provider_specific_config(self, mock_llm):
        mock_factory, _ = mock_llm
        LLMReranker({
            "provider": "openai",
            "llm": {
                "provider": "ollama",
                "config": {
                    "model": "llama3",
                    "ollama_base_url": "http://localhost:11434",
                },
            },
        })

        call_args = mock_factory.create.call_args
        llm_config = call_args[0][1]
        assert llm_config["ollama_base_url"] == "http://localhost:11434"
        assert llm_config["model"] == "llama3"

    def test_nested_llm_inherits_top_level_defaults(self, mock_llm):
        """Nested config should inherit temperature/max_tokens from top-level if not overridden."""
        mock_factory, _ = mock_llm
        LLMReranker({
            "provider": "openai",
            "temperature": 0.0,
            "max_tokens": 100,
            "llm": {
                "provider": "ollama",
                "config": {"model": "llama3"},
            },
        })

        call_args = mock_factory.create.call_args
        llm_config = call_args[0][1]
        assert llm_config["temperature"] == 0.0
        assert llm_config["max_tokens"] == 100

    def test_nested_llm_config_values_take_precedence(self, mock_llm):
        """Values explicitly set in nested config should not be overridden by top-level defaults."""
        mock_factory, _ = mock_llm
        LLMReranker({
            "provider": "openai",
            "model": "gpt-4o-mini",
            "temperature": 0.0,
            "max_tokens": 100,
            "llm": {
                "provider": "ollama",
                "config": {
                    "model": "custom-model",
                    "temperature": 0.5,
                    "max_tokens": 200,
                },
            },
        })

        call_args = mock_factory.create.call_args
        llm_config = call_args[0][1]
        assert llm_config["model"] == "custom-model"
        assert llm_config["temperature"] == 0.5
        assert llm_config["max_tokens"] == 200

    def test_nested_llm_falls_back_to_top_level_provider(self, mock_llm):
        """If nested llm dict has no 'provider', use top-level provider."""
        mock_factory, _ = mock_llm
        LLMReranker({
            "provider": "anthropic",
            "model": "claude-3-haiku",
            "llm": {
                "config": {"model": "claude-3-sonnet"},
            },
        })

        call_args = mock_factory.create.call_args
        assert call_args[0][0] == "anthropic"
        assert call_args[0][1]["model"] == "claude-3-sonnet"

    def test_nested_llm_with_empty_config(self, mock_llm):
        """Nested llm with no config dict should still work, using top-level defaults."""
        mock_factory, _ = mock_llm
        LLMReranker({
            "provider": "openai",
            "model": "gpt-4o-mini",
            "llm": {"provider": "ollama"},
        })

        call_args = mock_factory.create.call_args
        assert call_args[0][0] == "ollama"
        llm_config = call_args[0][1]
        assert llm_config["model"] == "gpt-4o-mini"
        assert llm_config["temperature"] == 0.0
        assert llm_config["max_tokens"] == 100

    def test_nested_llm_with_none_config(self, mock_llm):
        """Nested llm with config: None should still work, using top-level defaults."""
        mock_factory, _ = mock_llm
        LLMReranker({
            "provider": "openai",
            "model": "gpt-4o-mini",
            "llm": {"provider": "ollama", "config": None},
        })

        call_args = mock_factory.create.call_args
        assert call_args[0][0] == "ollama"
        llm_config = call_args[0][1]
        assert llm_config["model"] == "gpt-4o-mini"

    def test_nested_llm_inherits_top_level_api_key(self, mock_llm):
        """Top-level api_key should be inherited by nested config if not already set."""
        mock_factory, _ = mock_llm
        LLMReranker({
            "provider": "openai",
            "api_key": "sk-top-level",
            "llm": {
                "provider": "openai",
                "config": {"model": "gpt-4o"},
            },
        })

        call_args = mock_factory.create.call_args
        llm_config = call_args[0][1]
        assert llm_config["api_key"] == "sk-top-level"

    def test_nested_llm_config_api_key_not_overridden(self, mock_llm):
        """If nested config already has api_key, top-level api_key should not override it."""
        mock_factory, _ = mock_llm
        LLMReranker({
            "provider": "openai",
            "api_key": "sk-top-level",
            "llm": {
                "provider": "openai",
                "config": {"model": "gpt-4o", "api_key": "sk-nested"},
            },
        })

        call_args = mock_factory.create.call_args
        llm_config = call_args[0][1]
        assert llm_config["api_key"] == "sk-nested"
