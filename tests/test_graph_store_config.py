from mem0.graphs.configs import GraphStoreConfig, KuzuConfig


def test_graph_store_allows_none_for_neo4j():
    config = GraphStoreConfig(provider="neo4j", config=None)
    assert config.config is None


def test_graph_store_kuzu_defaults_when_config_missing():
    config = GraphStoreConfig(provider="kuzu", config=None)
    assert isinstance(config.config, KuzuConfig)
    assert config.config.db == ":memory:"
