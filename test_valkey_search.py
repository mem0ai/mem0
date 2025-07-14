#!/usr/bin/env python3
"""
Script to test HNSW search functionality in Valkey
"""

import struct

import valkey


def main():
    print("Connecting to Valkey...")
    r = valkey.Valkey(host="localhost", port=6379, decode_responses=False)

    # Create query vector (similar to vec1 - should match Alice's data better)
    print("Creating query vector...")
    query_vec = [0.9] + [0.1] * 1535
    query_bytes = struct.pack("f" * 1536, *query_vec)
    print(f"Query vector size: {len(query_bytes)} bytes")

    # Test 1: Basic vector search
    print("\n=== Test 1: Basic Vector Search ===")
    try:
        result = r.execute_command(
            "FT.SEARCH",
            "mem0_test",
            "*=>[KNN 2 @embedding $vec_param AS vector_score]",
            "PARAMS",
            "2",
            "vec_param",
            query_bytes,
            "RETURN",
            "3",
            "memory_id",
            "memory",
            "vector_score",
        )
        print("Search results:")
        print(result)
    except Exception as e:
        print(f"Error in basic search: {e}")

    # Test 2: Vector search with custom EF_RUNTIME
    print("\n=== Test 2: Vector Search with Custom EF_RUNTIME ===")
    try:
        result = r.execute_command(
            "FT.SEARCH",
            "mem0_test",
            "*=>[KNN 2 @embedding $vec_param EF_RUNTIME 20 AS vector_score]",
            "PARAMS",
            "2",
            "vec_param",
            query_bytes,
            "RETURN",
            "3",
            "memory_id",
            "memory",
            "vector_score",
        )
        print("Search results with EF_RUNTIME 20:")
        print(result)
    except Exception as e:
        print(f"Error in EF_RUNTIME search: {e}")

    # Test 3: Filtered vector search (user_id filter)
    print("\n=== Test 3: Filtered Vector Search (Alice only) ===")
    try:
        result = r.execute_command(
            "FT.SEARCH",
            "mem0_test",
            "@user_id:{alice}=>[KNN 2 @embedding $vec_param AS vector_score]",
            "PARAMS",
            "2",
            "vec_param",
            query_bytes,
            "RETURN",
            "3",
            "memory_id",
            "memory",
            "vector_score",
        )
        print("Filtered search results (Alice only):")
        print(result)
    except Exception as e:
        print(f"Error in filtered search: {e}")

    # Test 4: Filtered vector search with custom EF_RUNTIME
    print("\n=== Test 4: Filtered Vector Search with Custom EF_RUNTIME ===")
    try:
        result = r.execute_command(
            "FT.SEARCH",
            "mem0_test",
            "@user_id:{alice}=>[KNN 2 @embedding $vec_param EF_RUNTIME 20 AS vector_score]",
            "PARAMS",
            "2",
            "vec_param",
            query_bytes,
            "RETURN",
            "3",
            "memory_id",
            "memory",
            "vector_score",
        )
        print("Filtered search results with EF_RUNTIME 20:")
        print(result)
    except Exception as e:
        print(f"Error in filtered EF_RUNTIME search: {e}")

    # Test 5: Check index info
    print("\n=== Test 5: Index Information ===")
    try:
        info = r.execute_command("FT.INFO", "mem0_test")
        print("Index info:")
        print(info)
    except Exception as e:
        print(f"Error getting index info: {e}")


if __name__ == "__main__":
    main()
