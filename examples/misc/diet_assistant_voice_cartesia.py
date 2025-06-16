from agno.agent import Agent
from agno.tools.cartesia import CartesiaTools
from agno.utils.audio import write_audio_to_file
from mem0 import MemoryClient

memory_client = MemoryClient()

# Simple agent that remembers food preferences
diet_agent = Agent(
    name="Chef Memory Assistant",
    description="Food assistant that remembers your preferences",
    instructions="""
You are a helpful food assistant with memory. Follow these steps SEQUENTIALLY for EVERY response:

    1. Analyze the user's food request and check their dietary preferences from memory
    2. Formulate a personalized food recommendation based on their restrictions and preferences
    3. Analyze the emotion/tone needed for the response (friendly, helpful, cautious for allergies)
    4. Call `list_voices` to see available voice options
    5. Select an appropriate voice that matches the helpful, friendly tone
    6. Call `text_to_speech` to generate audio for your complete food recommendation

    IMPORTANT: You MUST always generate speech audio for your response. Every response should end with spoken audio.

    Remember details like:
    - Dietary restrictions (vegetarian, allergies, etc.)
    - Favorite cuisines and flavors
    - Cooking preferences and time constraints
    - Meal timing preferences
""",
    tools=[CartesiaTools()],
    show_tool_calls=True,
)


def chat(message: str, user_id="default-user"):
    # Get what we remember about this user
    memories_result = memory_client.search(
        query=message,
        user_id=user_id,
        limit=3
    )

    # Add memory context to the message
    memories = [f"- {result['memory']}" for result in memories_result]
    memory_context = "Memories about user that might be relevant:\n" + "\n".join(memories)

    # Get response with voice
    response = diet_agent.run(f"{memory_context}\nUser: {message}")
    conversation = [
        {"role": "user", "content": message},
        {"role": "assistant", "content": str(response)}
    ]
    # Add to memory
    memory_client.add(conversation, user_id=user_id)

    if response.audio:
        write_audio_to_file(
            response.audio[0].base64_audio,
            filename="food_recommendation.mp3"
        )
        print("🎵 Audio saved as food_recommendation.mp3")

    return response.content


print(chat("What did I tell you about my dietary restrictions?"))

