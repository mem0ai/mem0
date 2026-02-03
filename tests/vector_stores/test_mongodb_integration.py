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
    from pymongo.operations import SearchIndexModel
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


def test_knnvector_to_vectorsearch_migration():
    """
    Tests the automatic migration from legacy knnVector index to vectorSearch index.
    
    This test:
    1. Creates a legacy knnVector index manually (simulating old code)
    2. Inserts test data
    3. Initializes MongoDB class (triggers auto-healing)
    4. Verifies index was migrated to vectorSearch
    5. Verifies data is preserved
    6. Verifies search works with new index
    """
    if not TESTCONTAINERS_AVAILABLE:
        pytest.skip("Testcontainers not installed. Run: pip install testcontainers")

    print("\n🔄 Testing knnVector → vectorSearch Migration...")
    
    with AtlasContainer() as container:
        container.wait_for_ready()
        time.sleep(2)  # Safety buffer
        
        uri = container.get_connection_url()
        db_name = "test_migration"
        collection_name = "migration_test_vectors"
        index_name = f"{collection_name}_vector_index"
        embedding_dims = 3
        
        # Step 1: Create legacy knnVector index manually
        # ---------------------------------------------------------
        print("📝 Step 1: Creating legacy knnVector index...")
        client = MongoClient(uri)
        database = client[db_name]
        collection = database[collection_name]
        
        # Create collection
        collection.insert_one({"_id": 0, "placeholder": True})
        collection.delete_one({"_id": 0})
        
        # Create legacy knnVector index using the EXACT old format from the original code
        # This replicates the old MongoDB class behavior before migration
        print("📝 Step 1a: Creating legacy knnVector index using old format...")
        
        # Use the exact old format - no 'type' field at SearchIndexModel level, 
        # and 'mappings' structure with 'knnVector' field type
        legacy_index = SearchIndexModel(
            name=index_name,
            definition={
                "mappings": {
                    "dynamic": False,
                    "fields": {
                        "embedding": {
                            "type": "knnVector",  # Old knnVector format
                            "dimensions": embedding_dims,
                            "similarity": "cosine",
                        }
                    },
                }
            },
        )
        
        try:
            collection.create_search_index(legacy_index)
            print("✅ Legacy knnVector index creation initiated")
        except PyMongoError as e:
            # MongoDB Atlas Local may not support creating knnVector indexes
            # If this happens, we can't test the migration from real knnVector
            pytest.skip(
                f"MongoDB Atlas Local does not support creating knnVector indexes. "
                f"Error: {e}. "
                f"This test requires a MongoDB instance that supports knnVector index creation."
            )
        
        # Wait for legacy index to be ready (polling)
        print("⏳ Step 1b: Waiting for legacy index to be ready...")
        max_wait = 120  # Increased timeout for index creation
        start_time = time.time()
        legacy_ready = False
        
        while (time.time() - start_time) < max_wait:
            indexes = list(collection.list_search_indexes(name=index_name))
            if indexes:
                idx = indexes[0]
                if idx.get("queryable") is True:
                    legacy_ready = True
                    break
                status = idx.get("status", "unknown")
                print(f"   Index status: {status}, queryable: {idx.get('queryable', False)}")
            time.sleep(2)
        
        if not legacy_ready:
            pytest.fail(f"Legacy index did not become ready within {max_wait} seconds")
        
        # Verify legacy index exists and has knnVector type in the old format
        print("🔍 Step 1c: Verifying legacy index structure...")
        indexes = list(collection.list_search_indexes(name=index_name))
        assert len(indexes) == 1, "Legacy index should exist"
        
        legacy_index_obj = indexes[0]
        legacy_def = legacy_index_obj.get("latestDefinition", {})
        
        # Check for old format: mappings.fields.embedding.type == "knnVector"
        legacy_mappings = legacy_def.get("mappings", {})
        if not legacy_mappings:
            # If mappings is not present, check if it was converted already
            pytest.fail(
                f"Legacy index does not have 'mappings' structure. "
                f"Index may have been auto-converted. Definition: {legacy_def}"
            )
        
        legacy_fields = legacy_mappings.get("fields", {})
        if not legacy_fields:
            pytest.fail(
                f"Legacy index does not have 'fields' in mappings. "
                f"Definition: {legacy_def}"
            )
        
        embedding_field = legacy_fields.get("embedding", {})
        if not embedding_field:
            pytest.fail(
                f"Legacy index does not have 'embedding' field. "
                f"Fields: {list(legacy_fields.keys())}"
            )
        
        # Verify it's using the old knnVector format
        field_type = embedding_field.get("type")
        assert field_type == "knnVector", (
            f"Expected knnVector type, got: {field_type}. "
            f"Embedding field: {embedding_field}, "
            f"Full definition: {legacy_def}"
        )
        assert embedding_field.get("dimensions") == embedding_dims
        print("✅ Verified legacy knnVector index structure (old format confirmed)")
        
        # Step 2: Insert test data using legacy index
        # ---------------------------------------------------------
        print("📥 Step 2: Inserting test data...")
        test_vectors = [
            [1.0, 0.0, 0.0],  # Vector A
            [0.0, 1.0, 0.0],  # Vector B
            [0.0, 0.0, 1.0],  # Vector C
        ]
        test_payloads = [
            {"name": "vector_a", "category": "test"},
            {"name": "vector_b", "category": "test"},
            {"name": "vector_c", "category": "migration"},
        ]
        test_ids = ["legacy_a", "legacy_b", "legacy_c"]
        
        for vec, payload, vec_id in zip(test_vectors, test_payloads, test_ids):
            collection.insert_one({"_id": vec_id, "embedding": vec, "payload": payload})
        
        # Verify data was inserted
        assert collection.count_documents({}) == 3
        print("✅ Test data inserted (3 vectors)")
        
        # Step 3: Initialize MongoDB class (triggers auto-healing)
        # ---------------------------------------------------------
        print("🔧 Step 3: Initializing MongoDB class (should trigger auto-healing)...")
        store = MongoDB(
            db_name=db_name,
            collection_name=collection_name,
            embedding_model_dims=embedding_dims,
            mongo_uri=uri,
            wait_for_index_ready=True,  # Wait for migration to complete
            index_creation_timeout=300,  # 5 minutes for migration
        )
        print("✅ MongoDB class initialized")
        
        # Step 4: Verify index was migrated to vectorSearch
        # ---------------------------------------------------------
        print("🔍 Step 4: Verifying index migration...")
        
        # Wait a moment for migration to complete if it's still in progress
        print("⏳ Waiting for migration to complete...")
        time.sleep(5)
        
        indexes = list(collection.list_search_indexes(name=index_name))
        assert len(indexes) == 1, f"Index should exist after migration. Found {len(indexes)} indexes."
        
        migrated_index = indexes[0]
        migrated_def = migrated_index.get("latestDefinition", {})
        
        # Debug: Print the definition to see what we got
        print(f"   Index definition: {migrated_def}")
        print(f"   Index queryable: {migrated_index.get('queryable')}")
        print(f"   Index status: {migrated_index.get('status')}")
        
        # Verify the old mappings structure is gone
        old_mappings = migrated_def.get("mappings", {})
        assert not old_mappings or not old_mappings.get("fields"), (
            f"Old mappings structure should be gone. Found: {old_mappings}"
        )
        
        # Verify field structure changed from knnVector to vector (new format)
        migrated_fields = migrated_def.get("fields", [])
        assert len(migrated_fields) == 1, f"Should have one vector field, got: {len(migrated_fields)}"
        assert migrated_fields[0].get("type") == "vector", (
            f"Field type should be 'vector', got: {migrated_fields[0].get('type')}"
        )
        assert migrated_fields[0].get("path") == "embedding", (
            f"Field path should be 'embedding', got: {migrated_fields[0].get('path')}"
        )
        assert migrated_fields[0].get("numDimensions") == embedding_dims, (
            f"Dimensions should match {embedding_dims}, got: {migrated_fields[0].get('numDimensions')}"
        )
        
        # Verify index is queryable (may take a moment after migration)
        if not migrated_index.get("queryable"):
            print("⏳ Waiting for migrated index to become queryable...")
            max_wait = 120
            start_time = time.time()
            while (time.time() - start_time) < max_wait:
                indexes = list(collection.list_search_indexes(name=index_name))
                if indexes and indexes[0].get("queryable"):
                    break
                time.sleep(2)
            else:
                pytest.fail(f"Migrated index did not become queryable within {max_wait} seconds")
        
        assert migrated_index.get("queryable") is True, "Migrated index should be queryable"
        print("✅ Index successfully migrated to vectorSearch format (fields array with vector type)")
        
        # Step 5: Verify data is preserved
        # ---------------------------------------------------------
        print("💾 Step 5: Verifying data preservation...")
        assert collection.count_documents({}) == 3, "All data should be preserved"
        
        # Verify individual documents
        doc_a = collection.find_one({"_id": "legacy_a"})
        assert doc_a is not None, "Document A should exist"
        assert doc_a["payload"]["name"] == "vector_a", "Payload should be preserved"
        assert doc_a["embedding"] == [1.0, 0.0, 0.0], "Vector should be preserved"
        
        doc_b = collection.find_one({"_id": "legacy_b"})
        assert doc_b is not None, "Document B should exist"
        assert doc_b["payload"]["name"] == "vector_b", "Payload should be preserved"
        
        doc_c = collection.find_one({"_id": "legacy_c"})
        assert doc_c is not None, "Document C should exist"
        assert doc_c["payload"]["category"] == "migration", "Payload should be preserved"
        print("✅ All data preserved during migration")
        
        # Step 6: Verify search works with new index
        # ---------------------------------------------------------
        print("🔎 Step 6: Verifying search functionality with migrated index...")
        
        # Wait a moment for index to be fully ready
        time.sleep(3)
        
        # Test exact match search
        results = store.search(
            query="test search",
            vectors=[1.0, 0.0, 0.0],  # Should match vector_a
            limit=1
        )
        
        assert len(results) == 1, "Should find one result"
        assert results[0].id == "legacy_a", "Should find vector_a"
        assert results[0].score > 0.99, "Score should be high for exact match"
        assert results[0].payload["name"] == "vector_a", "Payload should be correct"
        print("✅ Search works correctly with migrated index")
        
        # Test filtered search
        filtered_results = store.search(
            query="test search",
            vectors=[0.0, 0.0, 1.0],  # Near vector_c
            limit=5,
            filters={"category": "migration"}
        )
        
        assert len(filtered_results) == 1, "Should find one filtered result"
        assert filtered_results[0].id == "legacy_c", "Should find vector_c"
        assert filtered_results[0].payload["category"] == "migration", "Filter should work"
        print("✅ Filtered search works correctly")
        
        # Cleanup
        print("🧹 Cleaning up migration test...")
        try:
            store.delete_col()
        except PyMongoError:
            pass
        client.close()
        
        print("✅ Migration test completed successfully!")