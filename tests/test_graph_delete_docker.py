"""
End-to-end tests for graph cleanup on memory deletion against real
Neo4j, Memgraph, and Apache AGE instances running in Docker.

Requires:
    docker run -d --name mem0-neo4j-test -p 7687:7687 -e NEO4J_AUTH=neo4j/testpassword neo4j:5.23
    docker run -d --name mem0-memgraph-test -p 7688:7687 memgraph/memgraph:latest
    docker run -d --name mem0-age-test -p 5432:5432 -e POSTGRES_USER=postgres -e POSTGRES_PASSWORD=testpassword -e POSTGRES_DB=testdb apache/age:latest

Tests are skipped automatically if the databases or required Python
packages are not available.
"""

import hashlib
import sys
import warnings
from unittest.mock import MagicMock

import pytest

warnings.filterwarnings("ignore")

EMBEDDING_DIMS = 64

# ---------------------------------------------------------------------------
# Deterministic embedding helper (shared across backends)
# ---------------------------------------------------------------------------


def _make_deterministic_embedder():
    cache = {}
    counter = [0]

    def embed(text, *args, **kwargs):
        t = text.lower().strip()
        if t not in cache:
            vec = [0.0] * EMBEDDING_DIMS
            idx = counter[0] % EMBEDDING_DIMS
            vec[idx] = 1.0
            h = hashlib.sha256(t.encode()).digest()
            for i in range(EMBEDDING_DIMS):
                vec[i] += float(h[i % len(h)]) / 25500.0
            norm = sum(v * v for v in vec) ** 0.5
            cache[t] = [v / norm for v in vec]
            counter[0] += 1
        return cache[t]

    mock = MagicMock()
    mock.embed.side_effect = embed
    mock.config.embedding_dims = EMBEDDING_DIMS
    return mock


def _make_mock_llm(entities, relations):
    """Create an LLM mock that returns specific entities and relations."""
    mock = MagicMock()

    def generate_response(messages, tools):
        tool_names = []
        for t in tools:
            if isinstance(t, dict):
                fn = t.get("function", t)
                tool_names.append(fn.get("name", ""))
            else:
                tool_names.append(getattr(t, "name", str(t)))

        if any("extract_entities" in n for n in tool_names):
            return {
                "tool_calls": [
                    {"name": "extract_entities", "arguments": {"entities": entities}}
                ]
            }
        elif any("establish" in n or "relation" in n for n in tool_names):
            return {
                "tool_calls": [
                    {"name": "establish_nodes_relations", "arguments": {"entities": relations}}
                ]
            }
        elif any("delete" in n for n in tool_names):
            return {"tool_calls": []}
        return {"tool_calls": []}

    mock.generate_response.side_effect = generate_response
    return mock


# ===========================================================================
# NEO4J
# ===========================================================================


def _neo4j_available():
    try:
        from langchain_neo4j import Neo4jGraph

        g = Neo4jGraph(
            url="bolt://localhost:7687",
            username="neo4j",
            password="testpassword",
            refresh_schema=False,
            driver_config={"notifications_min_severity": "OFF"},
        )
        g.query("RETURN 1")
        return True
    except Exception:
        return False


requires_neo4j = pytest.mark.skipif(not _neo4j_available(), reason="Neo4j not available")


@pytest.fixture
def neo4j_graph():
    """Create a Neo4j-backed MemoryGraph with mocked LLM/embedder."""
    from langchain_neo4j import Neo4jGraph
    from mem0.memory.graph_memory import MemoryGraph

    mg = MemoryGraph.__new__(MemoryGraph)
    mg.graph = Neo4jGraph(
        url="bolt://localhost:7687",
        username="neo4j",
        password="testpassword",
        refresh_schema=False,
        driver_config={"notifications_min_severity": "OFF"},
    )
    mg.graph.query("MATCH (n) DETACH DELETE n")

    mg.node_label = ":`__Entity__`"
    mg.llm_provider = "openai"
    mg.user_id = None
    mg.threshold = 0.99
    mg.embedding_model = _make_deterministic_embedder()
    mg.llm = MagicMock()
    mg.config = MagicMock()
    mg.config.graph_store.custom_prompt = None
    mg.config.graph_store.config.base_label = True

    yield mg

    mg.graph.query("MATCH (n) DETACH DELETE n")


@requires_neo4j
class TestNeo4jDeleteE2E:
    def _node_count(self, mg):
        return mg.graph.query("MATCH (n) RETURN count(n) AS cnt")[0]["cnt"]

    def _valid_edge_count(self, mg):
        return mg.graph.query(
            "MATCH ()-[r]->() WHERE r.valid IS NULL OR r.valid = true RETURN count(r) AS cnt"
        )[0]["cnt"]

    def _invalid_edge_count(self, mg):
        return mg.graph.query(
            "MATCH ()-[r]->() WHERE r.valid = false RETURN count(r) AS cnt"
        )[0]["cnt"]

    def test_add_creates_graph_data(self, neo4j_graph):
        mg = neo4j_graph
        mg.llm = _make_mock_llm(
            [{"entity": "Alice", "entity_type": "person"}, {"entity": "Bob", "entity_type": "person"}],
            [{"source": "Alice", "destination": "Bob", "relationship": "likes"}],
        )
        mg.add("Alice likes Bob", {"user_id": "u1"})
        assert self._node_count(mg) == 2
        assert self._valid_edge_count(mg) == 1

    def test_delete_soft_deletes_relationships(self, neo4j_graph):
        """Neo4j delete() should set r.valid=false (soft-delete), not hard-delete."""
        mg = neo4j_graph
        mg.llm = _make_mock_llm(
            [{"entity": "Alice", "entity_type": "person"}, {"entity": "Bob", "entity_type": "person"}],
            [{"source": "Alice", "destination": "Bob", "relationship": "likes"}],
        )
        mg.add("Alice likes Bob", {"user_id": "u1"})
        assert self._valid_edge_count(mg) == 1
        assert self._invalid_edge_count(mg) == 0

        mg.delete("Alice likes Bob", {"user_id": "u1"})

        assert self._valid_edge_count(mg) == 0
        assert self._invalid_edge_count(mg) == 1  # soft-deleted, not removed
        assert self._node_count(mg) == 2  # nodes preserved

    def test_delete_preserves_other_relationships(self, neo4j_graph):
        mg = neo4j_graph
        mg.llm = _make_mock_llm(
            [{"entity": "Alice", "entity_type": "person"}, {"entity": "Bob", "entity_type": "person"}],
            [{"source": "Alice", "destination": "Bob", "relationship": "likes"}],
        )
        mg.add("Alice likes Bob", {"user_id": "u1"})

        mg.llm = _make_mock_llm(
            [{"entity": "Alice", "entity_type": "person"}, {"entity": "Charlie", "entity_type": "person"}],
            [{"source": "Alice", "destination": "Charlie", "relationship": "knows"}],
        )
        mg.add("Alice knows Charlie", {"user_id": "u1"})
        assert self._valid_edge_count(mg) == 2

        mg.llm = _make_mock_llm(
            [{"entity": "Alice", "entity_type": "person"}, {"entity": "Bob", "entity_type": "person"}],
            [{"source": "Alice", "destination": "Bob", "relationship": "likes"}],
        )
        mg.delete("Alice likes Bob", {"user_id": "u1"})

        assert self._valid_edge_count(mg) == 1
        assert self._invalid_edge_count(mg) == 1

    def test_delete_user_isolation(self, neo4j_graph):
        mg = neo4j_graph
        mg.llm = _make_mock_llm(
            [{"entity": "Alice", "entity_type": "person"}, {"entity": "Bob", "entity_type": "person"}],
            [{"source": "Alice", "destination": "Bob", "relationship": "likes"}],
        )
        mg.add("Alice likes Bob", {"user_id": "u1"})
        mg.add("Alice likes Bob", {"user_id": "u2"})
        assert self._valid_edge_count(mg) == 2

        mg.delete("Alice likes Bob", {"user_id": "u1"})
        assert self._valid_edge_count(mg) == 1

    def test_delete_all_hard_deletes(self, neo4j_graph):
        mg = neo4j_graph
        mg.llm = _make_mock_llm(
            [{"entity": "Alice", "entity_type": "person"}, {"entity": "Bob", "entity_type": "person"}],
            [{"source": "Alice", "destination": "Bob", "relationship": "likes"}],
        )
        mg.add("Alice likes Bob", {"user_id": "u1"})
        assert self._node_count(mg) == 2

        mg.delete_all({"user_id": "u1"})
        assert self._node_count(mg) == 0

    def test_add_delete_add_cycle(self, neo4j_graph):
        mg = neo4j_graph
        mg.llm = _make_mock_llm(
            [{"entity": "Alice", "entity_type": "person"}, {"entity": "Bob", "entity_type": "person"}],
            [{"source": "Alice", "destination": "Bob", "relationship": "likes"}],
        )

        mg.add("Alice likes Bob", {"user_id": "u1"})
        assert self._valid_edge_count(mg) == 1

        mg.delete("Alice likes Bob", {"user_id": "u1"})
        assert self._valid_edge_count(mg) == 0

        mg.add("Alice likes Bob", {"user_id": "u1"})
        assert self._valid_edge_count(mg) == 1


# ===========================================================================
# MEMGRAPH
# ===========================================================================


def _memgraph_available():
    try:
        from langchain_memgraph.graphs.memgraph import Memgraph

        g = Memgraph("bolt://localhost:7688", "memgraph", "memgraph")
        g.query("RETURN 1")
        return True
    except Exception:
        return False


requires_memgraph = pytest.mark.skipif(
    not _memgraph_available(), reason="Memgraph not available"
)


@pytest.fixture
def memgraph_graph():
    """Create a Memgraph-backed MemoryGraph with mocked LLM/embedder."""
    from langchain_memgraph.graphs.memgraph import Memgraph
    from mem0.memory.memgraph_memory import MemoryGraph

    mg = MemoryGraph.__new__(MemoryGraph)
    mg.graph = Memgraph("bolt://localhost:7688", "memgraph", "memgraph")
    mg.graph.query("MATCH (n) DETACH DELETE n")

    try:
        mg.graph.query("DROP VECTOR INDEX memzero;")
    except Exception:
        pass
    mg.graph.query(
        f"CREATE VECTOR INDEX memzero ON :Entity(embedding) "
        f"WITH CONFIG {{'dimension': {EMBEDDING_DIMS}, 'capacity': 1000, 'metric': 'cos'}};"
    )
    try:
        mg.graph.query("CREATE INDEX ON :Entity(user_id);")
    except Exception:
        pass
    try:
        mg.graph.query("CREATE INDEX ON :Entity;")
    except Exception:
        pass

    mg.llm_provider = "openai"
    mg.user_id = None
    mg.threshold = 0.99
    mg.embedding_model = _make_deterministic_embedder()
    mg.llm = MagicMock()
    mg.config = MagicMock()
    mg.config.graph_store.custom_prompt = None
    mg.config.embedder.config = {"embedding_dims": EMBEDDING_DIMS}

    yield mg

    mg.graph.query("MATCH (n) DETACH DELETE n")


@requires_memgraph
class TestMemgraphDeleteE2E:
    def _node_count(self, mg):
        return mg.graph.query("MATCH (n:Entity) RETURN count(n) AS cnt")[0]["cnt"]

    def _edge_count(self, mg):
        return mg.graph.query("MATCH ()-[r]->() RETURN count(r) AS cnt")[0]["cnt"]

    def test_add_creates_graph_data(self, memgraph_graph):
        mg = memgraph_graph
        mg.llm = _make_mock_llm(
            [{"entity": "Alice", "entity_type": "person"}, {"entity": "Bob", "entity_type": "person"}],
            [{"source": "Alice", "destination": "Bob", "relationship": "likes"}],
        )
        mg.add("Alice likes Bob", {"user_id": "u1"})
        assert self._node_count(mg) == 2
        assert self._edge_count(mg) == 1

    def test_delete_hard_deletes_relationships(self, memgraph_graph):
        """Memgraph delete() should hard-delete the relationship (DELETE r)."""
        mg = memgraph_graph
        mg.llm = _make_mock_llm(
            [{"entity": "Alice", "entity_type": "person"}, {"entity": "Bob", "entity_type": "person"}],
            [{"source": "Alice", "destination": "Bob", "relationship": "likes"}],
        )
        mg.add("Alice likes Bob", {"user_id": "u1"})
        assert self._edge_count(mg) == 1

        mg.delete("Alice likes Bob", {"user_id": "u1"})

        assert self._edge_count(mg) == 0
        assert self._node_count(mg) == 2

    def test_delete_preserves_other_relationships(self, memgraph_graph):
        mg = memgraph_graph
        mg.llm = _make_mock_llm(
            [{"entity": "Alice", "entity_type": "person"}, {"entity": "Bob", "entity_type": "person"}],
            [{"source": "Alice", "destination": "Bob", "relationship": "likes"}],
        )
        mg.add("Alice likes Bob", {"user_id": "u1"})

        mg.llm = _make_mock_llm(
            [{"entity": "Alice", "entity_type": "person"}, {"entity": "Charlie", "entity_type": "person"}],
            [{"source": "Alice", "destination": "Charlie", "relationship": "knows"}],
        )
        mg.add("Alice knows Charlie", {"user_id": "u1"})
        assert self._edge_count(mg) == 2

        mg.llm = _make_mock_llm(
            [{"entity": "Alice", "entity_type": "person"}, {"entity": "Bob", "entity_type": "person"}],
            [{"source": "Alice", "destination": "Bob", "relationship": "likes"}],
        )
        mg.delete("Alice likes Bob", {"user_id": "u1"})

        assert self._edge_count(mg) == 1

    def test_delete_user_isolation(self, memgraph_graph):
        mg = memgraph_graph
        mg.llm = _make_mock_llm(
            [{"entity": "Alice", "entity_type": "person"}, {"entity": "Bob", "entity_type": "person"}],
            [{"source": "Alice", "destination": "Bob", "relationship": "likes"}],
        )
        mg.add("Alice likes Bob", {"user_id": "u1"})
        mg.add("Alice likes Bob", {"user_id": "u2"})
        assert self._edge_count(mg) == 2

        mg.delete("Alice likes Bob", {"user_id": "u1"})
        assert self._edge_count(mg) == 1

    def test_delete_all_hard_deletes(self, memgraph_graph):
        mg = memgraph_graph
        mg.llm = _make_mock_llm(
            [{"entity": "Alice", "entity_type": "person"}, {"entity": "Bob", "entity_type": "person"}],
            [{"source": "Alice", "destination": "Bob", "relationship": "likes"}],
        )
        mg.add("Alice likes Bob", {"user_id": "u1"})
        assert self._node_count(mg) == 2

        mg.delete_all({"user_id": "u1"})
        assert self._node_count(mg) == 0
        assert self._edge_count(mg) == 0

    def test_add_delete_add_cycle(self, memgraph_graph):
        mg = memgraph_graph
        mg.llm = _make_mock_llm(
            [{"entity": "Alice", "entity_type": "person"}, {"entity": "Bob", "entity_type": "person"}],
            [{"source": "Alice", "destination": "Bob", "relationship": "likes"}],
        )
        mg.add("Alice likes Bob", {"user_id": "u1"})
        assert self._edge_count(mg) == 1

        mg.delete("Alice likes Bob", {"user_id": "u1"})
        assert self._edge_count(mg) == 0

        mg.add("Alice likes Bob", {"user_id": "u1"})
        assert self._edge_count(mg) == 1


# ===========================================================================
# APACHE AGE
# ===========================================================================


def _age_available():
    try:
        import age

        ag = age.connect(
            host="localhost",
            port=5432,
            dbname="testdb",
            user="postgres",
            password="testpassword",
        )
        with ag.connection.cursor() as cur:
            cur.execute("CREATE EXTENSION IF NOT EXISTS age;")
            cur.execute("SET search_path = ag_catalog, '$user', public;")
        ag.connection.commit()
        ag.close()
        return True
    except Exception:
        return False


requires_age = pytest.mark.skipif(not _age_available(), reason="Apache AGE not available")


@pytest.fixture
def age_graph():
    """Create an Apache AGE-backed MemoryGraph with mocked LLM/embedder."""
    import age

    from mem0.memory.apache_age_memory import MemoryGraph

    graph_name = "mem0_test_delete"

    ag = age.connect(
        graph=graph_name,
        host="localhost",
        port=5432,
        dbname="testdb",
        user="postgres",
        password="testpassword",
    )
    with ag.connection.cursor() as cur:
        cur.execute("CREATE EXTENSION IF NOT EXISTS age;")
        cur.execute("SET search_path = ag_catalog, '$user', public;")
    ag.connection.commit()
    age.setUpAge(ag.connection, graph_name)
    ag.connection.commit()

    mg = MemoryGraph.__new__(MemoryGraph)
    mg.ag = ag
    mg.graph_name = graph_name
    mg.llm_provider = "openai"
    mg.user_id = None
    mg.threshold = 0.99
    mg.embedding_model = _make_deterministic_embedder()
    mg.llm = MagicMock()
    mg.config = MagicMock()
    mg.config.graph_store.custom_prompt = None

    try:
        ag.execCypher("MATCH (n) DETACH DELETE n")
        ag.commit()
    except Exception:
        ag.rollback()

    yield mg

    try:
        ag.execCypher("MATCH (n) DETACH DELETE n")
        ag.commit()
    except Exception:
        ag.rollback()
    ag.close()


def _age_node_count(mg):
    cursor = mg.ag.execCypher("MATCH (n) RETURN count(n)", cols=["cnt"])
    rows = cursor.fetchall()
    return rows[0][0] if rows else 0


def _age_edge_count(mg):
    cursor = mg.ag.execCypher("MATCH ()-[r]->() RETURN count(r)", cols=["cnt"])
    rows = cursor.fetchall()
    return rows[0][0] if rows else 0


@requires_age
class TestApacheAgeDeleteE2E:

    def test_add_creates_graph_data(self, age_graph):
        mg = age_graph
        mg.llm = _make_mock_llm(
            [{"entity": "Alice", "entity_type": "person"}, {"entity": "Bob", "entity_type": "person"}],
            [{"source": "Alice", "destination": "Bob", "relationship": "likes"}],
        )
        mg.add("Alice likes Bob", {"user_id": "u1"})
        assert _age_node_count(mg) == 2
        assert _age_edge_count(mg) == 1

    def test_delete_hard_deletes_relationships(self, age_graph):
        """Apache AGE delete() should hard-delete the relationship."""
        mg = age_graph
        mg.llm = _make_mock_llm(
            [{"entity": "Alice", "entity_type": "person"}, {"entity": "Bob", "entity_type": "person"}],
            [{"source": "Alice", "destination": "Bob", "relationship": "likes"}],
        )
        mg.add("Alice likes Bob", {"user_id": "u1"})
        assert _age_edge_count(mg) == 1

        mg.delete("Alice likes Bob", {"user_id": "u1"})

        assert _age_edge_count(mg) == 0
        assert _age_node_count(mg) == 2

    def test_delete_preserves_other_relationships(self, age_graph):
        mg = age_graph
        mg.llm = _make_mock_llm(
            [{"entity": "Alice", "entity_type": "person"}, {"entity": "Bob", "entity_type": "person"}],
            [{"source": "Alice", "destination": "Bob", "relationship": "likes"}],
        )
        mg.add("Alice likes Bob", {"user_id": "u1"})

        mg.llm = _make_mock_llm(
            [{"entity": "Alice", "entity_type": "person"}, {"entity": "Charlie", "entity_type": "person"}],
            [{"source": "Alice", "destination": "Charlie", "relationship": "knows"}],
        )
        mg.add("Alice knows Charlie", {"user_id": "u1"})
        assert _age_edge_count(mg) == 2

        mg.llm = _make_mock_llm(
            [{"entity": "Alice", "entity_type": "person"}, {"entity": "Bob", "entity_type": "person"}],
            [{"source": "Alice", "destination": "Bob", "relationship": "likes"}],
        )
        mg.delete("Alice likes Bob", {"user_id": "u1"})
        assert _age_edge_count(mg) == 1

    def test_delete_user_isolation(self, age_graph):
        mg = age_graph
        mg.llm = _make_mock_llm(
            [{"entity": "Alice", "entity_type": "person"}, {"entity": "Bob", "entity_type": "person"}],
            [{"source": "Alice", "destination": "Bob", "relationship": "likes"}],
        )
        mg.add("Alice likes Bob", {"user_id": "u1"})
        mg.add("Alice likes Bob", {"user_id": "u2"})
        assert _age_edge_count(mg) == 2

        mg.delete("Alice likes Bob", {"user_id": "u1"})
        assert _age_edge_count(mg) == 1

    def test_delete_all_hard_deletes(self, age_graph):
        mg = age_graph
        mg.llm = _make_mock_llm(
            [{"entity": "Alice", "entity_type": "person"}, {"entity": "Bob", "entity_type": "person"}],
            [{"source": "Alice", "destination": "Bob", "relationship": "likes"}],
        )
        mg.add("Alice likes Bob", {"user_id": "u1"})
        assert _age_node_count(mg) == 2

        mg.delete_all({"user_id": "u1"})
        assert _age_node_count(mg) == 0
        assert _age_edge_count(mg) == 0

    def test_add_delete_add_cycle(self, age_graph):
        mg = age_graph
        mg.llm = _make_mock_llm(
            [{"entity": "Alice", "entity_type": "person"}, {"entity": "Bob", "entity_type": "person"}],
            [{"source": "Alice", "destination": "Bob", "relationship": "likes"}],
        )
        mg.add("Alice likes Bob", {"user_id": "u1"})
        assert _age_edge_count(mg) == 1

        mg.delete("Alice likes Bob", {"user_id": "u1"})
        assert _age_edge_count(mg) == 0

        mg.add("Alice likes Bob", {"user_id": "u1"})
        assert _age_edge_count(mg) == 1


# ===========================================================================
# NEPTUNE (tested via Neo4j OpenCypher — same query language)
# ===========================================================================


def _neptune_test_available():
    """Neptune uses OpenCypher — we test NeptuneBase.delete() against Neo4j."""
    try:
        # Mock langchain_aws so NeptuneBase can be imported without AWS deps
        sys.modules.setdefault("langchain_aws", MagicMock())
        sys.modules.setdefault("botocore", MagicMock())
        sys.modules.setdefault("botocore.config", MagicMock())

        from mem0.graphs.neptune.base import NeptuneBase  # noqa: F401
        from langchain_neo4j import Neo4jGraph

        g = Neo4jGraph(
            url="bolt://localhost:7687",
            username="neo4j",
            password="testpassword",
            refresh_schema=False,
            driver_config={"notifications_min_severity": "OFF"},
        )
        g.query("RETURN 1")
        return True
    except Exception:
        return False


requires_neptune_test = pytest.mark.skipif(
    not _neptune_test_available(),
    reason="Neo4j not available (used as OpenCypher backend for Neptune tests)",
)


def _make_concrete_neptune_subclass():
    """Create a concrete NeptuneBase subclass for testing, backed by Neo4j."""
    # Ensure mocks are in place for import
    sys.modules.setdefault("langchain_aws", MagicMock())
    sys.modules.setdefault("botocore", MagicMock())
    sys.modules.setdefault("botocore.config", MagicMock())

    from mem0.graphs.neptune.base import NeptuneBase

    class TestableNeptune(NeptuneBase):
        def __init__(self):
            pass

        def _delete_entities_cypher(self, source, destination, relationship, user_id):
            cypher = f"""
                MATCH (n:`__Entity__` {{name: $source_name, user_id: $user_id}})
                -[r:{relationship}]->
                (m:`__Entity__` {{name: $dest_name, user_id: $user_id}})
                DELETE r
                RETURN n.name AS source, m.name AS target, type(r) AS relationship
            """
            return cypher, {"source_name": source, "dest_name": destination, "user_id": user_id}

        def _delete_all_cypher(self, filters):
            return (
                "MATCH (n:`__Entity__` {user_id: $user_id}) DETACH DELETE n",
                {"user_id": filters["user_id"]},
            )

        # Stubs for abstract methods not used in delete path
        def _add_entities_by_source_cypher(self, *a, **kw): pass
        def _add_entities_by_destination_cypher(self, *a, **kw): pass
        def _add_relationship_entities_cypher(self, *a, **kw): pass
        def _add_new_entities_cypher(self, *a, **kw): pass
        def _search_source_node_cypher(self, *a, **kw): pass
        def _search_destination_node_cypher(self, *a, **kw): pass
        def _get_all_cypher(self, *a, **kw): pass
        def _search_graph_db_cypher(self, *a, **kw): pass

    return TestableNeptune


@pytest.fixture
def neptune_graph():
    """NeptuneBase subclass backed by a real Neo4j container."""
    from langchain_neo4j import Neo4jGraph

    cls = _make_concrete_neptune_subclass()
    mg = cls()
    mg.graph = Neo4jGraph(
        url="bolt://localhost:7687",
        username="neo4j",
        password="testpassword",
        refresh_schema=False,
        driver_config={"notifications_min_severity": "OFF"},
    )
    mg.graph.query("MATCH (n) DETACH DELETE n")

    mg.node_label = ":`__Entity__`"
    mg.llm_provider = "openai"
    mg.user_id = None
    mg.threshold = 0.99
    mg.embedding_model = _make_deterministic_embedder()
    mg.llm = MagicMock()
    mg.config = MagicMock()
    mg.config.graph_store.custom_prompt = None

    yield mg

    mg.graph.query("MATCH (n) DETACH DELETE n")


def _neptune_node_count(mg):
    return mg.graph.query("MATCH (n) RETURN count(n) AS cnt")[0]["cnt"]


def _neptune_edge_count(mg):
    return mg.graph.query("MATCH ()-[r]->() RETURN count(r) AS cnt")[0]["cnt"]


def _neptune_create_entities(mg, user_id):
    """Create test entities directly via Cypher."""
    mg.graph.query(f"""
        CREATE (a:`__Entity__` {{name: 'alice', user_id: '{user_id}'}})
        CREATE (b:`__Entity__` {{name: 'bob', user_id: '{user_id}'}})
        CREATE (a)-[:likes]->(b)
    """)


@requires_neptune_test
class TestNeptuneDeleteE2E:
    """Test NeptuneBase.delete() using Neo4j as the OpenCypher backend.

    Neptune uses standard OpenCypher, the same query language as Neo4j.
    This validates that:
    - NeptuneBase.delete() correctly calls _delete_entities(to_be_deleted, user_id) with a string
    - The generated Cypher from _delete_entities_cypher runs correctly
    - User isolation works
    """

    def test_delete_removes_relationship(self, neptune_graph):
        mg = neptune_graph
        mg.llm = _make_mock_llm(
            [{"entity": "Alice", "entity_type": "person"}, {"entity": "Bob", "entity_type": "person"}],
            [{"source": "Alice", "destination": "Bob", "relationship": "likes"}],
        )
        _neptune_create_entities(mg, "u1")
        assert _neptune_edge_count(mg) == 1

        mg.delete("Alice likes Bob", {"user_id": "u1"})

        assert _neptune_edge_count(mg) == 0
        assert _neptune_node_count(mg) == 2

    def test_delete_user_isolation(self, neptune_graph):
        mg = neptune_graph
        mg.llm = _make_mock_llm(
            [{"entity": "Alice", "entity_type": "person"}, {"entity": "Bob", "entity_type": "person"}],
            [{"source": "Alice", "destination": "Bob", "relationship": "likes"}],
        )
        _neptune_create_entities(mg, "u1")
        _neptune_create_entities(mg, "u2")
        assert _neptune_edge_count(mg) == 2

        mg.delete("Alice likes Bob", {"user_id": "u1"})
        assert _neptune_edge_count(mg) == 1

    def test_delete_passes_user_id_string_not_dict(self, neptune_graph):
        """Verify NeptuneBase.delete() passes filters['user_id'] (string) to _delete_entities."""
        mg = neptune_graph
        mg.llm = _make_mock_llm(
            [{"entity": "Alice", "entity_type": "person"}, {"entity": "Bob", "entity_type": "person"}],
            [{"source": "Alice", "destination": "Bob", "relationship": "likes"}],
        )

        original = mg._delete_entities
        call_args = []

        def spy(to_be_deleted, user_id):
            call_args.append(("to_be_deleted", to_be_deleted, "user_id", user_id))
            return original(to_be_deleted, user_id)

        mg._delete_entities = spy

        _neptune_create_entities(mg, "u1")
        mg.delete("Alice likes Bob", {"user_id": "u1"})

        assert len(call_args) == 1
        assert call_args[0][3] == "u1"
        assert isinstance(call_args[0][3], str)

    def test_delete_all(self, neptune_graph):
        mg = neptune_graph
        _neptune_create_entities(mg, "u1")
        assert _neptune_node_count(mg) == 2

        mg.delete_all({"user_id": "u1"})
        assert _neptune_node_count(mg) == 0

    def test_add_delete_add_cycle(self, neptune_graph):
        mg = neptune_graph
        mg.llm = _make_mock_llm(
            [{"entity": "Alice", "entity_type": "person"}, {"entity": "Bob", "entity_type": "person"}],
            [{"source": "Alice", "destination": "Bob", "relationship": "likes"}],
        )
        _neptune_create_entities(mg, "u1")
        assert _neptune_edge_count(mg) == 1

        mg.delete("Alice likes Bob", {"user_id": "u1"})
        assert _neptune_edge_count(mg) == 0

        _neptune_create_entities(mg, "u1")
        assert _neptune_edge_count(mg) == 1
