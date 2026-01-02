from qdrant_client import QdrantClient

client = QdrantClient("http://localhost:6333")

# 1. Corrected method name: collection_exists
if client.collection_exists("openmemory"):
    print("Collection 'openmemory' found!")
    
    # 2. Scroll requires 'collection_name' as a keyword or first argument
    # It returns a tuple: (points, next_page_offset)
    points, _ = client.scroll(collection_name="openmemory", limit=10)
    
    if not points:
        print("Collection is empty (no points found).")
    for point in points:
        print(f"ID: {point.id} | Payload: {point.payload}")
else:
    print("Collection 'openmemory' does not exist.")
