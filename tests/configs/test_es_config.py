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
    err = None
    try:
        config = {
            "host": "localhost",
            "port": 9200,
            "user": "elastic",
            "password": "password",
            "headers": "not-a-dict",  # This should be a dictionary
        }
        _ = ElasticsearchConfig(**config)
    except ValueError as e:
        err = e
        print(f"Expected error: {e}")
    assert err is not None

    try:
        config = {
            "host": "localhost",
            "port": 9200,
            "user": "elastic",
            "password": "password",
            "headers": {"x-extra-info": 123},  # Key and Value must be a string
        }
        _ = ElasticsearchConfig(**config)
    except ValueError as e:
        err = e
        print(f"Expected error: {e}")
    assert err is not None
