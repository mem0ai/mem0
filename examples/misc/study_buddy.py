"""
Create your personal AI Study Buddy that remembers what you’ve studied (and where you struggled),
helps  with spaced repetition and topic review, personalizes responses using your past interactions.
Supports both text and PDF/image inputs.

In order to run this file, you need to set up your Mem0 API at Mem0 platform and also need a OpenAI API key.
export OPENAI_API_KEY="your_openai_api_key"
export MEM0_API_KEY="your_mem0_api_key"
"""

import asyncio

from agents import Agent, Runner

from mem0 import MemoryClient

client = MemoryClient()

# Define your study buddy agent
study_agent = Agent(
    name="StudyBuddy",
    instructions="""You are a helpful study coach. You:
- Track what the user has studied before
- Identify topics the user has struggled with (e.g., "I'm confused", "this is hard")
- Help with spaced repetition by suggesting topics to revisit based on last review time
- Personalize answers using stored memories
- Summarize PDFs or notes the user uploads""",
)


# Upload and store PDF to Mem0
def upload_pdf(pdf_url: str, user_id: str):
    pdf_message = {"role": "user", "content": {"type": "pdf_url", "pdf_url": {"url": pdf_url}}}
    client.add([pdf_message], user_id=user_id)
    print("✅ PDF uploaded and processed into memory.")


# Main interaction loop with your personal study buddy
async def study_buddy(user_id: str, topic: str, user_input: str):
    memories = client.search(f"{topic}", user_id=user_id)
    memory_context = "n".join(f"- {m['memory']}" for m in memories)

    prompt = f"""
You are helping the user study the topic: {topic}.
Here are past memories from previous sessions:
{memory_context}

Now respond to the user's new question or comment:
{user_input}
"""
    result = await Runner.run(study_agent, prompt)
    response = result.final_output

    client.add(
        [{"role": "user", "content": f"""Topic: {topic}nUser: {user_input}nnStudy Assistant: {response}"""}],
        user_id=user_id,
        metadata={"topic": topic},
    )

    return response


# Example usage
async def main():
    user_id = "Ajay"
    pdf_url = "https://pages.physics.ua.edu/staff/fabi/ph101/classnotes/8RotD101.pdf"
    upload_pdf(pdf_url, user_id)  # Upload a relevant lecture PDF to memory

    topic = "Lagrangian Mechanics"
    # Demonstrate tracking previously learned topics
    print(await study_buddy(user_id, topic, "Can you remind me of what we discussed about generalized coordinates?"))

    # Demonstrate weakness detection
    print(await study_buddy(user_id, topic, "I still don’t get what frequency domain really means."))

    # Demonstrate spaced repetition prompting
    topic = "Momentum Conservation"
    print(
        await study_buddy(
            user_id, topic, "I think we covered this last week. Is it time to review momentum conservation again?"
        )
    )


if __name__ == "__main__":
    asyncio.run(main())
