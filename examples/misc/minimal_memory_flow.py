"""
Minimal Mem0 OSS example: add, search, and delete a memory.

Requires:
  export OPENAI_API_KEY="your-openai-api-key"
  pip install mem0ai
"""

from mem0 import Memory


def main() -> None:
    memory = Memory()
    user_id = "demo-user"

    add_result = memory.add(
        "I prefer tea over coffee.",
        user_id=user_id,
        metadata={"category": "preferences"},
    )
    memory_id = add_result["results"][0]["id"]
    print(f"Added memory: {memory_id}")

    search_result = memory.search(
        "What drinks does the user like?",
        filters={"user_id": user_id},
    )
    print(f"Search hits: {len(search_result['results'])}")
    if search_result["results"]:
        print(f"Top result: {search_result['results'][0]['memory']}")

    memory.delete(memory_id=memory_id)
    print(f"Deleted memory: {memory_id}")

    after_delete = memory.search(
        "What drinks does the user like?",
        filters={"user_id": user_id},
    )
    print(f"Search hits after delete: {len(after_delete['results'])}")


if __name__ == "__main__":
    main()