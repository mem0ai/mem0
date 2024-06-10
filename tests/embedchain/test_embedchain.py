import os

import pytest
from chromadb.api.models.Collection import Collection

from embedchain import App
from embedchain.config import AppConfig, ChromaDbConfig
from embedchain.embedchain import EmbedChain
from embedchain.llm.base import BaseLlm
from embedchain.memory.base import ChatHistory
from embedchain.vectordb.chroma import ChromaDB

os.environ["OPENAI_API_KEY"] = "test-api-key"


@pytest.fixture
def app_instance():
    config = AppConfig(log_level="DEBUG", collect_metrics=False)
    return App(config=config)


def test_whole_app(app_instance, mocker):
    knowledge = "lorem ipsum dolor sit amet, consectetur adipiscing"

    mocker.patch.object(EmbedChain, "add")
    mocker.patch.object(EmbedChain, "_retrieve_from_database")
    mocker.patch.object(BaseLlm, "get_answer_from_llm", return_value=knowledge)
    mocker.patch.object(BaseLlm, "get_llm_model_answer", return_value=knowledge)
    mocker.patch.object(BaseLlm, "generate_prompt")
    mocker.patch.object(BaseLlm, "add_history")
    mocker.patch.object(ChatHistory, "delete", autospec=True)

    app_instance.add(knowledge, data_type="text")
    app_instance.query("What text did I give you?")
    app_instance.chat("What text did I give you?")

    assert BaseLlm.generate_prompt.call_count == 2
    app_instance.reset()


def test_add_after_reset(app_instance, mocker):
    mocker.patch("embedchain.vectordb.chroma.chromadb.Client")

    config = AppConfig(log_level="DEBUG", collect_metrics=False)
    chroma_config = ChromaDbConfig(allow_reset=True)
    db = ChromaDB(config=chroma_config)
    app_instance = App(config=config, db=db)

    # mock delete chat history
    mocker.patch.object(ChatHistory, "delete", autospec=True)

    app_instance.reset()

    app_instance.db.client.heartbeat()

    mocker.patch.object(Collection, "add")

    app_instance.db.collection.add(
        embeddings=[[1.1, 2.3, 3.2], [4.5, 6.9, 4.4], [1.1, 2.3, 3.2]],
        metadatas=[
            {"chapter": "3", "verse": "16"},
            {"chapter": "3", "verse": "5"},
            {"chapter": "29", "verse": "11"},
        ],
        ids=["id1", "id2", "id3"],
    )

    app_instance.reset()


def test_add_with_incorrect_content(app_instance, mocker):
    content = [{"foo": "bar"}]

    with pytest.raises(TypeError):
        app_instance.add(content, data_type="json")
