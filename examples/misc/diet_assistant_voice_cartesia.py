"""Simple Voice Agent with Memory: Personal Food Assistant.
A food assistant that remembers your dietary preferences and speaks recommendations
Powered by Agno + Cartesia + Mem0

export MEM0_API_KEY=your_mem0_api_key
export OPENAI_API_KEY=your_openai_api_key
export CARTESIA_API_KEY=your_cartesia_api_key
"""

from textwrap import dedent

from agno.agent import Agent
from agno.models.openai import OpenAIChat
from agno.tools.cartesia import CartesiaTools
from agno.utils.audio import write_audio_to_file

from mem0 import MemoryClient

memory_client = MemoryClient()
USER_ID = "food_user_01"

# Agent instructions
agent_instructions = dedent(
    """Follow these steps SEQUENTIALLY to provide personalized food recommendations with voice:
    1. Analyze the user's food request and identify what type of recommendation they need.
    2. Consider their dietary preferences, restrictions, and cooking habits from memory context.
    3. Generate a personalized food recommendation based on their stored preferences.
    4. Analyze the appropriate tone for the response (helpful, enthusiastic, cautious for allergies).
    5. Call `list_voices` to retrieve available voices.
    6. Select a voice that matches the helpful, friendly tone.
    7. Call `text_to_speech` to generate the final audio recommendation.
    """
)

# Simple agent that remembers food preferences
food_agent = Agent(
    name="Personal Food Assistant",
    description="Provides personalized food recommendations with memory and generates voice responses using Cartesia TTS tools.",
    instructions=agent_instructions,
    model=OpenAIChat(id="gpt-4o"),
    tools=[CartesiaTools(voice_localize_enabled=True)],
    show_tool_calls=True,
)


def get_food_recommendation(user_query: str, user_id):
    """Get food recommendation with memory context"""

    # Search memory for relevant food preferences
    memories_result = memory_client.search(query=user_query, user_id=user_id, limit=5)

    # Add memory context to the message
    memories = [f"- {result['memory']}" for result in memories_result]
    memory_context = "Memories about user that might be relevant:\n" + "\n".join(memories)

    # Combine memory context with user request
    full_request = f"""
    {memory_context}

    User: {user_query}

    Answer the user query based on provided context and create a voice note.
    """

    # Generate response with voice (same pattern as translator)
    food_agent.print_response(full_request)
    response = food_agent.run_response

    # Save audio file
    if response.audio:
        import time

        timestamp = int(time.time())
        filename = f"food_recommendation_{timestamp}.mp3"
        write_audio_to_file(
            response.audio[0].base64_audio,
            filename=filename,
        )
        print(f"Audio saved as {filename}")

    return response.content


def initialize_food_memory(user_id):
    """Initialize memory with food preferences"""
    messages = [
        {
            "role": "user",
            "content": "Hi, I'm Sarah. I'm vegetarian and lactose intolerant. I love spicy food, especially Thai and Indian cuisine.",
        },
        {
            "role": "assistant",
            "content": "Hello Sarah! I've noted that you're vegetarian, lactose intolerant, and love spicy Thai and Indian food.",
        },
        {
            "role": "user",
            "content": "I prefer quick breakfasts since I'm always rushing, but I like cooking elaborate dinners. I also meal prep on Sundays.",
        },
        {
            "role": "assistant",
            "content": "Got it! Quick breakfasts, elaborate dinners, and Sunday meal prep. I'll remember this for future recommendations.",
        },
        {
            "role": "user",
            "content": "I'm trying to eat more protein. I like quinoa, lentils, chickpeas, and tofu. I hate mushrooms though.",
        },
        {
            "role": "assistant",
            "content": "Perfect! I'll focus on protein-rich options like quinoa, lentils, chickpeas, and tofu, and avoid mushrooms.",
        },
    ]

    memory_client.add(messages, user_id=user_id)
    print("Food preferences stored in memory")


# Initialize the memory for the user once in order for the agent to learn the user preference
initialize_food_memory(user_id=USER_ID)

print(
    get_food_recommendation(
        "Which type of restaurants should I go tonight for dinner and cuisines preferred?", user_id=USER_ID
    )
)
# OUTPUT: 🎵 Audio saved as food_recommendation_1750162610.mp3
# For dinner tonight, considering your love for healthy spic optionsy, you could try a nice Thai, Indian, or Mexican restaurant.
# You might find dishes with quinoa, chickpeas, tofu, and fresh herbs delightful. Enjoy your dinner!
