import os

from mem0.vector_stores.db2 import Db2VectorStore

def main():
    # To run this example, ensure you have a running Db2 instance and ibm_db installed
    # pip install ibm_db
    
    # Configure your connection parameters
    db2_config = {
        "database": os.getenv("DB2_DATABASE", "testdb"),
        "host": os.getenv("DB2_HOST", "localhost"),
        "port": int(os.getenv("DB2_PORT", 50000)),
        "username": os.getenv("DB2_USERNAME", "db2inst1"),
        "password": os.getenv("DB2_PASSWORD", "password"),
        "ssl": False,
    }

    try:
        print("Initializing Db2VectorStore...")
        vector_store = Db2VectorStore(
            connection_params=db2_config, 
            table_name="mem0_example",
            distance_strategy="COSINE"
        )
        
        # 1. Insert vectors
        print("\n1. Inserting vectors...")
        vectors = [
            [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8],
            [0.8, 0.7, 0.6, 0.5, 0.4, 0.3, 0.2, 0.1],
            [0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1]
        ]
        payloads = [
            {"source": "docs", "author": "alice"},
            {"source": "web", "author": "bob"},
            {"source": "docs", "author": "charlie"}
        ]
        ids = ["v1", "v2", "v3"]
        vector_store.insert(vectors, payloads, ids)
        
        # 2. Get vector by ID
        print("\n2. Getting vector v1...")
        v1 = vector_store.get("v1")
        print(f"Retrieved: ID={v1.id}, payload={v1.payload}")
        
        # 3. List all vectors
        print("\n3. Listing all vectors...")
        all_vectors = vector_store.list()
        for v in all_vectors:
            print(f"ID={v.id}, payload={v.payload}")
            
        # 4. Search
        print("\n4. Searching for similar vectors to [0.1, 0.2, 0.3, ...]")
        query_vector = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8]
        results = vector_store.search("test query", query_vector, top_k=2)
        for r in results:
            print(f"Match: ID={r.id}, Score={r.score:.4f}, payload={r.payload}")
            
        # 5. Search with filters
        print("\n5. Searching with filter (source='docs')...")
        filter_results = vector_store.search(
            "test query", query_vector, top_k=2, filters={"source": "docs"}
        )
        for r in filter_results:
            print(f"Filtered Match: ID={r.id}, Score={r.score:.4f}, payload={r.payload}")
            
        # 6. Update a vector
        print("\n6. Updating vector v2 payload...")
        vector_store.update("v2", payload={"source": "web", "author": "bob_updated"})
        v2 = vector_store.get("v2")
        print(f"Updated v2 payload: {v2.payload}")
        
        # 7. Collection info
        print("\n7. Collection info...")
        info = vector_store.col_info()
        print(f"Info: {info}")
        
        # 8. Delete a vector
        print("\n8. Deleting vector v3...")
        vector_store.delete("v3")
        
        # 9. Reset / Delete Collection
        print("\n9. Resetting collection...")
        vector_store.reset()
        print("Done!")

    except ImportError:
        print("Please install ibm_db to run this example: pip install ibm_db")
    except Exception as e:
        print(f"An error occurred (make sure your Db2 instance is running and configured correctly): {e}")

if __name__ == "__main__":
    main()
