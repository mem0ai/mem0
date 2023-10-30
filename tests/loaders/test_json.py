import hashlib

from embedchain.loaders.json import JSONLoader


def test_load_data(mocker):
    content = "temp.json"

    mock_document = {
        "doc_id": hashlib.sha256((content + ", ".join(["content1", "content2"])).encode()).hexdigest(),
        "data": [
            {"content": "content1", "meta_data": {"url": content}},
            {"content": "content2", "meta_data": {"url": content}},
        ],
    }

    mocker.patch("embedchain.loaders.json.JSONLoader.load_data", return_value=mock_document)

    json_loader = JSONLoader()

    result = json_loader.load_data(content)

    assert "doc_id" in result
    assert "data" in result

    expected_data = [
        {"content": "content1", "meta_data": {"url": content}},
        {"content": "content2", "meta_data": {"url": content}},
    ]

    assert result["data"] == expected_data

    expected_doc_id = hashlib.sha256((content + ", ".join(["content1", "content2"])).encode()).hexdigest()
    assert result["doc_id"] == expected_doc_id
