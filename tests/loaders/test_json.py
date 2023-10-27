import hashlib
from unittest.mock import patch

from langchain.docstore.document import Document
from langchain.document_loaders.json_loader import \
    JSONLoader as LangchainJSONLoader

from embedchain.loaders.json import JSONLoader


def test_load_data():
    mock_document = [
        Document(page_content="content1", metadata={"seq_num": 1}),
        Document(page_content="content2", metadata={"seq_num": 2}),
    ]
    with patch.object(LangchainJSONLoader, "load", return_value=mock_document):
        content = "temp.json"

        result = JSONLoader.load_data(content)

        assert "doc_id" in result
        assert "data" in result

        expected_data = [
            {"content": "content1", "meta_data": {"url": content, "row": 1}},
            {"content": "content2", "meta_data": {"url": content, "row": 2}},
        ]

        assert result["data"] == expected_data

        expected_doc_id = hashlib.sha256((content + ", ".join(["content1", "content2"])).encode()).hexdigest()
        assert result["doc_id"] == expected_doc_id
