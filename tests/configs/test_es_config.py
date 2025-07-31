import pytest
from mem0.configs.vector_stores.elasticsearch import ElasticsearchConfig


def test_es_config():
    config = {"host": "localhost", "port": 9200, "user": "elastic", "password": "password"}
    ElasticsearchConfig(**config)
    print("ElasticsearchConfig initialized successfully with valid parameters.")


def test_es_valid_headers():
    config = {
        "host": "localhost",
        "port": 9200,
        "user": "elastic",
        "password": "password",
        "headers": {"x-extra-info": "my-mem0-instance"},
    }
    es_config = ElasticsearchConfig(**config)
    assert es_config.headers is not None and len(es_config.headers) == 1
    assert es_config.headers["x-extra-info"] == "my-mem0-instance"


def test_es_invalid_headers():
    base_config = {
        "host": "localhost",
        "port": 9200,
        "user": "elastic",
        "password": "password",
    }
    
    invalid_headers = [
        "not-a-dict",  # Non-dict headers
        {"x-extra-info": 123},  # Non-string values
        {123: "456"},  # Non-string keys
    ]
    
    for headers in invalid_headers:
        with pytest.raises(ValueError):
            config = {**base_config, "headers": headers}
            ElasticsearchConfig(**config)
