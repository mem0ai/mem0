"""
Integration tests for MongoDB Vector Store using Docker containers.

These tests use testcontainers to spin up a real MongoDB Atlas Local instance,
allowing us to verify the $vectorSearch pipeline and the fix for payload updates.

REQUIRES:
    pip install testcontainers pytest pymongo

RUNNING:
    pytest tests/vector_stores/test_mongodb_integration.py -v -s
"""

import time

import pytest

# -----------------------------------------------------------------------------
# Dependency Check
# -----------------------------------------------------------------------------
try:
    from pymongo import MongoClient
    from pymongo.errors import PyMongoError
    from testcontainers.core.container import DockerContainer

    TESTCONTAINERS_AVAILABLE = True
except ImportError:
    TESTCONTAINERS_AVAILABLE = False

# Import the class to be tested
# ADJUST THIS IMPORT if your file structure is different
from mem0.vector_stores.mongodb import MongoDB


# -----------------------------------------------------------------------------
# Custom Container Wrapper
# -----------------------------------------------------------------------------
class AtlasContainer(DockerContainer):
    """
    Wrapper for the MongoDB Atlas Local container.
    Standard Mongo images DO NOT support $vectorSearch; this specific image is required.
    """
    def __init__(self, image="mongodb/mongodb-atlas-local:latest", **kwargs):
        super(AtlasContainer, self).__init__(image, **kwargs)
        self.with_exposed_ports(27017)

    def get_connection_url(self) -> str:
        host = self.get_container_host_ip()
        port = self.get_exposed_port(27017)
        # Direct connection is required for the local atlas image
        return f"mongodb://{host}:{port}/?directConnection=true"

    def wait_for_ready(self, timeout=60):
        """
        Explicitly wait for the Mongo process to accept connections.
        Log waiting is unreliable with Mongo, so we ping the database.
        """
        start_time = time.time()
        url = self.get_connection_url()
        
        while time.time() - start_time < timeout:
            try:
                client = MongoClient(url, serverSelectionTimeoutMS=2000)
                # The 'ping' command is the truest test of readiness
                client.admin.command('ping')
                client.close()
                return True
            except Exception:
                time.sleep(1)
        
        raise TimeoutError(f"MongoDB did not become ready within {timeout} seconds.")


# -----------------------------------------------------------------------------
# Pytest Fixtures
# -----------------------------------------------------------------------------
@pytest.fixture(scope="module")
def mongo_store():
    """
    Spins up the container once for the entire test module.
    Yields an initialized MongoDB Vector Store connected to the container.
    """
    if not TESTCONTAINERS_AVAILABLE:
        pytest.skip("Testcontainers not installed. Run: pip install testcontainers")

    print("\n🐳 Starting MongoDB Atlas Local container (may take time to download)...")
    
    with AtlasContainer() as container:
        print("⏳ Waiting for MongoDB to accept connections...")
        container.wait_for_ready()
        
        # Extra safety buffer for internal search process initialization
        time.sleep(2)
        
        uri = container.get_connection_url()
        print(f"✅ MongoDB Ready at {uri}")

        # Initialize the Vector Store
        store = MongoDB(
            db_name="test_mem0",
            collection_name="integration_test_vectors",
            embedding_model_dims=3,  # 3D vectors for easy testing
            mongo_uri=uri
        )
        
        yield store
        
        # Cleanup
        print("\n🧹 Cleaning up test collection...")
        try:
            store.delete_col()
        except PyMongoError:
            # Silently ignore MongoDB errors during cleanup
            pass


# -----------------------------------------------------------------------------
# Test Cases
# -----------------------------------------------------------------------------
def test_vector_lifecycle(mongo_store):
    """
    Tests the full flow: Insert -> Search -> Update -> Delete.
    Verifies that $vectorSearch works and that Payload Updates merge correctly.
    """
    
    # 1. Insert Data
    # ---------------------------------------------------------
    print("📥 Inserting vectors...")
    vectors = [
        [1.0, 0.0, 0.0],  # A: Pure X
        [0.0, 1.0, 0.0],  # B: Pure Y
        [0.0, 0.0, 1.0],  # C: Pure Z
    ]
    payloads = [
        {"info": "A", "type": "axis", "mutable": 10},
        {"info": "B", "type": "axis", "mutable": 20},
        {"info": "C", "type": "other", "mutable": 30},
    ]
    ids = ["vec_a", "vec_b", "vec_c"]
    
    mongo_store.insert(vectors, payloads, ids)
    
    # CRITICAL: Wait for HNSW Indexing (Eventual Consistency)
    print("⏳ Waiting 3s for vector indexing...")
    time.sleep(3)

    # 2. Test Search (Exact Match)
    # ---------------------------------------------------------
    print("🔍 Searching for Vector A...")
    results = mongo_store.search(
        query="unused", 
        vectors=[1.0, 0.0, 0.0], 
        limit=1
    )
    
    assert len(results) == 1
    assert results[0].id == "vec_a"
    assert results[0].score > 0.99  # Cosine similarity of identical vectors is 1.0
    print("✅ Search OK")

    # 3. Test Filtering
    # ---------------------------------------------------------
    print("🔍 Testing Filter (Type='other')...")
    # Search near B, but filter for C
    results_filtered = mongo_store.search(
        query="unused",
        vectors=[0.0, 1.0, 0.0], 
        limit=5,
        filters={"type": "other"}
    )
    
    assert len(results_filtered) == 1
    assert results_filtered[0].id == "vec_c"
    assert results_filtered[0].payload["type"] == "other"
    print("✅ Filter OK")

    # 4. Test Partial Update (The Critical Fix)
    # ---------------------------------------------------------
    print("🔄 Testing Partial Payload Update...")
    # We update 'mutable' and add 'new_field'.
    # We expect 'info' and 'type' to remain UNCHANGED.
    mongo_store.update(
        vector_id="vec_a", 
        payload={"mutable": 999, "new_field": "test"}
    )
    
    updated_doc = mongo_store.get("vec_a")
    
    # Verify updates
    assert updated_doc.payload["mutable"] == 999
    assert updated_doc.payload["new_field"] == "test"
    
    # Verify preservation (Crucial)
    assert updated_doc.payload["info"] == "A"
    assert updated_doc.payload["type"] == "axis"
    print("✅ Partial Update OK (Fields merged correctly)")

    # 5. Test Delete
    # ---------------------------------------------------------
    print("🗑️ Testing Delete...")
    mongo_store.delete("vec_a")
    
    # Wait moment for consistency
    time.sleep(0.5)
    
    assert mongo_store.get("vec_a") is None
    print("✅ Delete OK")


def test_list_functionality(mongo_store):
    """
    Verifies the .list() method works with filters.
    """
    # Cleanup previous test data to be safe, or just insert new unique IDs
    # For speed, we'll just insert new IDs
    mongo_store.insert(
        vectors=[[0.5, 0.5, 0.0]], 
        payloads=[{"group": "admin"}], 
        ids=["user_admin"]
    )
    mongo_store.insert(
        vectors=[[0.1, 0.1, 0.1]], 
        payloads=[{"group": "user"}], 
        ids=["user_std"]
    )
    time.sleep(1)

    # List with filter
    results = mongo_store.list(filters={"group": "admin"})
    
    assert len(results) >= 1
    found_ids = [r.id for r in results]
    assert "user_admin" in found_ids
    assert "user_std" not in found_ids
    print("✅ List with Filter OK")