import warnings
from types import SimpleNamespace

import pytest

from mem0.configs.base import MemoryConfig
from mem0.configs.embeddings.base import BaseEmbedderConfig
from mem0.embeddings.aihubmix import AIHubMixEmbedding
from mem0.utils.factory import EmbedderFactory


@pytest.fixture(autouse=True)
def clean_aihubmix_env(monkeypatch):
    monkeypatch.delenv("AIHUBMIX_API_KEY", raising=False)
    monkeypatch.delenv("AIHUBMIX_BASE_URL", raising=False)


@pytest.fixture
def sdk(mocker):
    return mocker.patch("mem0.embeddings.openai.OpenAI")


def test_factory_and_isolated_config(sdk, monkeypatch):
    monkeypatch.setenv("AIHUBMIX_API_KEY", "env-key")
    config = MemoryConfig(embedder={"provider": "aihubmix", "config": {}})
    embedder = EmbedderFactory.create(config.embedder.provider, config.embedder.config, None)
    assert isinstance(embedder, AIHubMixEmbedding)
    assert embedder.config.model == "embed-v-4-0"
    assert embedder.config.embedding_dims == 1536
    sdk.assert_called_with(api_key="env-key", base_url="https://aihubmix.com/v1")

    original = BaseEmbedderConfig(aihubmix_base_url="https://explicit.example/v1")
    AIHubMixEmbedding(original)
    assert original.model is None
    assert original.embedding_dims is None
    assert original.openai_base_url is None
    assert BaseEmbedderConfig(*([None] * 19), "https://positional.example/v1").aihubmix_base_url == (
        "https://positional.example/v1"
    )


def test_key_and_url_precedence(sdk, monkeypatch):
    monkeypatch.setenv("AIHUBMIX_API_KEY", "env-key")
    monkeypatch.setenv("AIHUBMIX_BASE_URL", "https://env.example/v1")
    monkeypatch.setenv("OPENAI_API_KEY", "wrong")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://wrong.example/v1")
    monkeypatch.setenv("OPENAI_API_BASE", "https://wrong-legacy.example/v1")
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", DeprecationWarning)
        AIHubMixEmbedding()
    assert not any("OPENAI_API_BASE" in str(warning.message) for warning in caught)
    sdk.assert_called_with(api_key="env-key", base_url="https://env.example/v1")
    AIHubMixEmbedding(BaseEmbedderConfig(api_key="explicit", aihubmix_base_url="https://explicit.example/v1"))
    sdk.assert_called_with(api_key="explicit", base_url="https://explicit.example/v1")


def test_missing_key(sdk, monkeypatch):
    monkeypatch.delenv("AIHUBMIX_API_KEY", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "wrong")
    monkeypatch.setenv("OPENROUTER_API_KEY", "wrong")
    with pytest.raises(ValueError, match="AIHUBMIX_API_KEY"):
        AIHubMixEmbedding()
    sdk.assert_not_called()


@pytest.mark.parametrize("dims,expected", [(None, {}), (256, {"dimensions": 256})])
def test_embed_dimensions(sdk, dims, expected):
    embedder = AIHubMixEmbedding(BaseEmbedderConfig(api_key="key", embedding_dims=dims))
    sdk.return_value.embeddings.create.return_value = SimpleNamespace(data=[SimpleNamespace(index=0, embedding=[0.1])])
    assert embedder.embed("one\ntwo") == [0.1]
    sdk.return_value.embeddings.create.assert_called_once_with(
        input=["one two"], model="embed-v-4-0", encoding_format="float", **expected
    )


def test_batch_order_chunking_and_empty(sdk):
    embedder = AIHubMixEmbedding(BaseEmbedderConfig(api_key="key"))

    def create(**kwargs):
        return SimpleNamespace(
            data=[SimpleNamespace(index=i, embedding=[float(i)]) for i in reversed(range(len(kwargs["input"])))]
        )

    # Every response is deliberately reversed; sorting must restore input order.
    sdk.return_value.embeddings.create.side_effect = create
    assert embedder.embed_batch([]) == []
    sdk.return_value.embeddings.create.assert_not_called()
    result = embedder.embed_batch([str(i) for i in range(101)])
    assert result == [[float(i)] for i in range(100)] + [[0.0]]
    calls = sdk.return_value.embeddings.create.call_args_list
    assert len(calls) == 2
    assert len(calls[0].kwargs["input"]) == 100
    assert len(calls[1].kwargs["input"]) == 1
    assert all("dimensions" not in call.kwargs for call in calls)


def test_batch_count_mismatch(sdk):
    embedder = AIHubMixEmbedding(BaseEmbedderConfig(api_key="key", embedding_dims=256))
    sdk.return_value.embeddings.create.return_value = SimpleNamespace(data=[SimpleNamespace(index=0, embedding=[0.1])])
    with pytest.raises(ValueError, match="returned 1 embeddings for 2 texts"):
        embedder.embed_batch(["a", "b"])
    assert sdk.return_value.embeddings.create.call_args.kwargs["dimensions"] == 256
