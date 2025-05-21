"""
Create your personal AI Assistant powered by memory that supports both text and images and remembers your preferences

In order to run this file, you need to set up your Mem0 API at Mem0 platform and also need a OpenAI API key.
export OPENAI_API_KEY="your_openai_api_key"
export MEM0_API_KEY="your_mem0_api_key"
"""

import base64
from pathlib import Path

from agno.agent import Agent
from agno.media import Image
from agno.models.openai import OpenAIChat

from mem0 import MemoryClient

# Initialize the Mem0 client
client = MemoryClient()

# Define the agent
agent = Agent(
    name="Personal Agent",
    model=OpenAIChat(id="gpt-4o"),
    description="You are a helpful personal agent that helps me with day to day activities."
    "You can process both text and images.",
    markdown=True,
)


# Function to handle user input with memory integration with support for images
def chat_user(user_input: str = None, user_id: str = "user_123", image_path: str = None):
    if image_path:
        with open(image_path, "rb") as image_file:
            base64_image = base64.b64encode(image_file.read()).decode("utf-8")

        # First: the text message
        text_msg = {"role": "user", "content": user_input}

        # Second: the image message
        image_msg = {
            "role": "user",
            "content": {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}},
        }

        # Send both as separate message objects
        client.add([text_msg, image_msg], user_id=user_id, output_format="v1.1")
        print("✅ Image uploaded and stored in memory.")

    if user_input:
        memories = client.search(user_input, user_id=user_id)
        memory_context = "\n".join(f"- {m['memory']}" for m in memories)

        prompt = f"""
You are a helpful personal assistant who helps user with his day-to-day activities and keep track of everything.

Your task is to:
1. Analyze the given image (if present) and extract meaningful details to answer the user's question.
2. Use your past memory of the user to personalize your answer.
3. Combine the image content and memory to generate a helpful, context-aware response.

Here is what remember about the user:
{memory_context}

User question:
{user_input}
"""
        if image_path:
            response = agent.run(prompt, images=[Image(filepath=Path(image_path))])
        else:
            response = agent.run(prompt)
        client.add(f"User: {user_input}\nAssistant: {response.content}", user_id=user_id)
        return response.content

    return "No user input or image provided."


# Example Usage
user_id = "user_123"
print(chat_user("What did I ask you to remind me about?", user_id))
# # OUTPUT: You asked me to remind you to call your mom tomorrow. 📞
#
print(chat_user("When is my test?", user_id=user_id))
# OUTPUT: Your pilot's test is on your birthday, which is in five days. You're turning 25!
# Good luck with your preparations, and remember to take some time to relax amidst the studying.

print(
    chat_user(
        "This is the picture of what I brought with me in the trip to Bahamas",
        image_path="travel_items.jpeg",  # this will be added to Mem0 memory
        user_id=user_id,
    )
)
print(chat_user("hey can you quickly tell me if brought my sunglasses to my trip, not able to find", user_id=user_id))
# OUTPUT: Yes, you did bring your sunglasses on your trip to the Bahamas along with your laptop, face masks and other items..
# Since you can't find them now, perhaps check the pockets of jackets you wore or in your luggage compartments.
