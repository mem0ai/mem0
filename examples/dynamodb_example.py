"""
Example demonstrating the use of DynamoDB for mem0 storage.
"""

import json
import os
import time

from openai import OpenAI

from mem0.dynamodb.config import DynamoDBConversationConfig, DynamoDBGraphConfig

# Set your OpenAI API key
openai_api_key = os.environ.get("OPENAI_API_KEY")
if not openai_api_key:
    print("Warning: OPENAI_API_KEY environment variable not set")
    
openai_client = OpenAI(api_key=openai_api_key)

# Create a simplified example that just uses the DynamoDB graph store directly
def graph_store_example():
    """An example that demonstrates using the DynamoDB graph store with multiple topics."""
    from mem0.dynamodb.graph_store import DynamoDBMemoryGraph

    # Create the graph store
    graph_config = DynamoDBGraphConfig(
        table_name="Mem0Graph",
        region="us-east-1",
        enable_gsi=True
    )
    
    graph_store = DynamoDBMemoryGraph(graph_config)
    
    # Create memory nodes about colors
    print("\n=== Creating Color-Related Memories ===")
    blue_node_id = graph_store.create_memory_node(
        memory_id=None,  # Auto-generate ID
        content="My favorite color is blue",
        metadata={"topic": "colors", "importance": "high"}
    )
    print(f"Created memory node about blue: {blue_node_id}")
    
    sky_node_id = graph_store.create_memory_node(
        memory_id=None,
        content="The sky is blue on clear days",
        metadata={"topic": "colors", "importance": "medium"}
    )
    print(f"Created memory node about sky: {sky_node_id}")
    
    green_node_id = graph_store.create_memory_node(
        memory_id=None,
        content="Green is the color of grass and leaves",
        metadata={"topic": "colors", "importance": "medium"}
    )
    print(f"Created memory node about green: {green_node_id}")
    
    # Create memory nodes about taste
    print("\n=== Creating Taste-Related Memories ===")
    sweet_node_id = graph_store.create_memory_node(
        memory_id=None,
        content="I enjoy sweet foods like chocolate and honey",
        metadata={"topic": "taste", "importance": "high"}
    )
    print(f"Created memory node about sweet taste: {sweet_node_id}")
    
    sour_node_id = graph_store.create_memory_node(
        memory_id=None,
        content="Lemons and limes have a sour taste",
        metadata={"topic": "taste", "importance": "medium"}
    )
    print(f"Created memory node about sour taste: {sour_node_id}")
    
    spicy_node_id = graph_store.create_memory_node(
        memory_id=None,
        content="Chili peppers can be very spicy",
        metadata={"topic": "taste", "importance": "medium"}
    )
    print(f"Created memory node about spicy taste: {spicy_node_id}")
    
    # Create relationships between color nodes
    print("\n=== Creating Relationships Between Color Memories ===")
    graph_store.create_relationship(
        source_id=blue_node_id,
        target_id=sky_node_id,
        relationship_type="RELATED_TO",
        properties={"strength": "high"}
    )
    
    # Create relationships between taste nodes
    print("\n=== Creating Relationships Between Taste Memories ===")
    graph_store.create_relationship(
        source_id=sweet_node_id,
        target_id=sour_node_id,
        relationship_type="CONTRASTS_WITH",
        properties={"strength": "high"}
    )
    
    # Query for color-related memories
    print("\n=== Querying for Color-Related Memories ===")
    blue_related = graph_store.get_related_memories(blue_node_id)
    print("Memories related to 'blue':")
    for memory in blue_related:
        print(f"- {memory['content']}")
        print(f"  Relationship: {memory['relationship']}")
        print(f"  Properties: {memory.get('edge_properties', {})}")
    
    # Query for taste-related memories
    print("\n=== Querying for Taste-Related Memories ===")
    sweet_related = graph_store.get_related_memories(sweet_node_id)
    print("Memories related to 'sweet':")
    for memory in sweet_related:
        print(f"- {memory['content']}")
        print(f"  Relationship: {memory['relationship']}")
        print(f"  Properties: {memory.get('edge_properties', {})}")
    
    return blue_node_id, sweet_node_id

# Create a simplified example that just uses the DynamoDB conversation store directly
def conversation_store_example():
    """An example that demonstrates using the DynamoDB conversation store with multiple topics."""
    from mem0.dynamodb.conversation_store import DynamoDBConversationStore

    # Create the conversation store
    conv_config = DynamoDBConversationConfig(
        table_name="Mem0Conversations",
        region="us-east-1",
        ttl_enabled=True,
        ttl_days=30
    )
    
    conv_store = DynamoDBConversationStore(conv_config)
    
    # Store conversations about colors
    print("\n=== Storing Color-Related Conversations ===")
    user_id = "test_user"
    
    color_messages_1 = [
        {"role": "user", "content": "What's your favorite color?"},
        {"role": "assistant", "content": "I don't have personal preferences, but many people like blue."}
    ]
    
    color_conversation_id_1 = conv_store.store_conversation(
        user_id=user_id,
        messages=color_messages_1,
        metadata={"topic": "colors"}
    )
    print(f"Stored color conversation 1 with ID: {color_conversation_id_1}")
    
    color_messages_2 = [
        {"role": "user", "content": "Why is the sky blue?"},
        {"role": "assistant", "content": "The sky appears blue because air molecules scatter blue light more than other colors."}
    ]
    
    color_conversation_id_2 = conv_store.store_conversation(
        user_id=user_id,
        messages=color_messages_2,
        metadata={"topic": "colors"}
    )
    print(f"Stored color conversation 2 with ID: {color_conversation_id_2}")
    
    # Store conversations about taste
    print("\n=== Storing Taste-Related Conversations ===")
    
    taste_messages_1 = [
        {"role": "user", "content": "What are the basic taste sensations?"},
        {"role": "assistant", "content": "The five basic taste sensations are sweet, sour, salty, bitter, and umami."}
    ]
    
    taste_conversation_id_1 = conv_store.store_conversation(
        user_id=user_id,
        messages=taste_messages_1,
        metadata={"topic": "taste"}
    )
    print(f"Stored taste conversation 1 with ID: {taste_conversation_id_1}")
    
    taste_messages_2 = [
        {"role": "user", "content": "Why do some people like spicy food?"},
        {"role": "assistant", "content": "Some people enjoy spicy food because capsaicin triggers pain receptors that release endorphins."}
    ]
    
    taste_conversation_id_2 = conv_store.store_conversation(
        user_id=user_id,
        messages=taste_messages_2,
        metadata={"topic": "taste"}
    )
    print(f"Stored taste conversation 2 with ID: {taste_conversation_id_2}")
    
    # Add a small delay to ensure all data is stored
    time.sleep(1)
    
    # Retrieve all conversations for the user
    print("\n=== Retrieving All Conversations ===")
    all_conversations = conv_store.get_conversations_for_user(user_id, limit=10)
    print(f"Found {len(all_conversations)} conversations for user {user_id}")
    
    # Filter conversations by topic
    print("\n=== Filtering Conversations by Topic ===")
    color_conversations = []
    taste_conversations = []
    
    for conv in all_conversations:
        metadata = conv.get('metadata', {})
        # Handle both string and dict metadata
        if isinstance(metadata, str):
            metadata = json.loads(metadata)
            
        topic = metadata.get('topic')
        if topic == 'colors':
            color_conversations.append(conv)
        elif topic == 'taste':
            taste_conversations.append(conv)
    
    print(f"Found {len(color_conversations)} conversations about colors")
    for conv in color_conversations:
        messages = conv['messages']
        if isinstance(messages, str):
            messages = json.loads(messages)
            
        print(f"- Conversation ID: {conv['conversation_id']}")
        print(f"  User: {messages[0]['content']}")
        print(f"  Assistant: {messages[1]['content']}")
    
    print(f"\nFound {len(taste_conversations)} conversations about taste")
    for conv in taste_conversations:
        messages = conv['messages']
        if isinstance(messages, str):
            messages = json.loads(messages)
            
        print(f"- Conversation ID: {conv['conversation_id']}")
        print(f"  User: {messages[0]['content']}")
        print(f"  Assistant: {messages[1]['content']}")
    
    return color_conversation_id_1, taste_conversation_id_1

def main():
    """Main function to run the example."""
    print("=== DynamoDB Graph Store Example ===")
    blue_node_id, sweet_node_id = graph_store_example()
    
    print("\n=== DynamoDB Conversation Store Example ===")
    color_conversation_id, taste_conversation_id = conversation_store_example()
    
    print("\nExample completed successfully!")
    print(f"Created color node ID: {blue_node_id}")
    print(f"Created taste node ID: {sweet_node_id}")
    print(f"Created color conversation ID: {color_conversation_id}")
    print(f"Created taste conversation ID: {taste_conversation_id}")

if __name__ == "__main__":
    main()
