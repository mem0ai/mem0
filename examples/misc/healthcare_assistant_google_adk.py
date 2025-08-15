import asyncio
import warnings

from google.adk.agents import Agent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from mem0 import MemoryClient

warnings.filterwarnings("ignore", category=DeprecationWarning)


# Initialize Mem0 client
mem0_client = MemoryClient()


# Define Memory Tools
def save_patient_info(information: str) -> dict:
    """Saves important patient information to memory."""
    print(f"Storing patient information: {information[:30]}...")

    # Get user_id from session state or use default
    user_id = getattr(save_patient_info, "user_id", "default_user")

    # Store in Mem0
    mem0_client.add(
        [{"role": "user", "content": information}],
        user_id=user_id,
        run_id="healthcare_session",
        metadata={"type": "patient_information"},
    )

    return {"status": "success", "message": "Information saved"}


def retrieve_patient_info(query: str) -> str:
    """Retrieves relevant patient information from memory."""
    print(f"Searching for patient information: {query}")

    # Get user_id from session state or use default
    user_id = getattr(retrieve_patient_info, "user_id", "default_user")

    # Search Mem0
    results = mem0_client.search(
        query,
        user_id=user_id,
        run_id="healthcare_session",
        limit=5,
        threshold=0.7,  # Higher threshold for more relevant results
    )

    if not results:
        return "I don't have any relevant memories about this topic."

    memories = [f"• {result['memory']}" for result in results]
    return "Here's what I remember that might be relevant:\n" + "\n".join(memories)


# Define Healthcare Tools
def schedule_appointment(date: str, time: str, reason: str) -> dict:
    """Schedules a doctor's appointment."""
    # In a real app, this would connect to a scheduling system
    appointment_id = f"APT-{hash(date + time) % 10000}"

    return {
        "status": "success",
        "appointment_id": appointment_id,
        "confirmation": f"Appointment scheduled for {date} at {time} for {reason}",
        "message": "Please arrive 15 minutes early to complete paperwork.",
    }


# Create the Healthcare Assistant Agent
healthcare_agent = Agent(
    name="healthcare_assistant",
    model="gemini-1.5-flash",  # Using Gemini for healthcare assistant
    description="Healthcare assistant that helps patients with health information and appointment scheduling.",
    instruction="""You are a helpful Healthcare Assistant with memory capabilities.

Your primary responsibilities are to:
1. Remember patient information using the 'save_patient_info' tool when they share symptoms, conditions, or preferences.
2. Retrieve past patient information using the 'retrieve_patient_info' tool when relevant to the current conversation.
3. Help schedule appointments using the 'schedule_appointment' tool.

IMPORTANT GUIDELINES:
- Always be empathetic, professional, and helpful.
- Save important patient information like symptoms, conditions, allergies, and preferences.
- Check if you have relevant patient information before asking for details they may have shared previously.
- Make it clear you are not a doctor and cannot provide medical diagnosis or treatment.
- For serious symptoms, always recommend consulting a healthcare professional.
- Keep all patient information confidential.
""",
    tools=[save_patient_info, retrieve_patient_info, schedule_appointment],
)

# Set Up Session and Runner
session_service = InMemorySessionService()

# Define constants for the conversation
APP_NAME = "healthcare_assistant_app"
USER_ID = "Alex"
SESSION_ID = "session_001"

# Create a session
session = session_service.create_session(app_name=APP_NAME, user_id=USER_ID, session_id=SESSION_ID)

# Create the runner
runner = Runner(agent=healthcare_agent, app_name=APP_NAME, session_service=session_service)


# Interact with the Healthcare Assistant
async def call_agent_async(query, runner, user_id, session_id):
    """Sends a query to the agent and returns the final response."""
    print(f"\n>>> Patient: {query}")

    # Format the user's message
    content = types.Content(role="user", parts=[types.Part(text=query)])

    # Set user_id for tools to access
    save_patient_info.user_id = user_id
    retrieve_patient_info.user_id = user_id

    # Run the agent
    async for event in runner.run_async(user_id=user_id, session_id=session_id, new_message=content):
        if event.is_final_response():
            if event.content and event.content.parts:
                response = event.content.parts[0].text
                print(f"<<< Assistant: {response}")
                return response

    return "No response received."


# Example conversation flow
async def run_conversation():
    # First interaction - patient introduces themselves with key information
    await call_agent_async(
        "Hi, I'm Alex. I've been having headaches for the past week, and I have a penicillin allergy.",
        runner=runner,
        user_id=USER_ID,
        session_id=SESSION_ID,
    )

    # Request for health information
    await call_agent_async(
        "Can you tell me more about what might be causing my headaches?",
        runner=runner,
        user_id=USER_ID,
        session_id=SESSION_ID,
    )

    # Schedule an appointment
    await call_agent_async(
        "I think I should see a doctor. Can you help me schedule an appointment for next Monday at 2pm?",
        runner=runner,
        user_id=USER_ID,
        session_id=SESSION_ID,
    )

    # Test memory - should remember patient name, symptoms, and allergy
    await call_agent_async(
        "What medications should I avoid for my headaches?", runner=runner, user_id=USER_ID, session_id=SESSION_ID
    )


# Interactive mode
async def interactive_mode():
    """Run an interactive chat session with the healthcare assistant."""
    print("=== Healthcare Assistant Interactive Mode ===")
    print("Enter 'exit' to quit at any time.")

    # Get user information
    patient_id = input("Enter patient ID (or press Enter for default): ").strip() or USER_ID
    session_id = f"session_{hash(patient_id) % 1000:03d}"

    # Create session for this user
    session_service.create_session(app_name=APP_NAME, user_id=patient_id, session_id=session_id)

    print(f"\nStarting conversation with patient ID: {patient_id}")
    print("Type your message and press Enter.")

    while True:
        user_input = input("\n>>> Patient: ").strip()
        if user_input.lower() in ["exit", "quit", "bye"]:
            print("Ending conversation. Thank you!")
            break

        await call_agent_async(user_input, runner=runner, user_id=patient_id, session_id=session_id)


# Main execution
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Healthcare Assistant with Memory")
    parser.add_argument("--demo", action="store_true", help="Run the demo conversation")
    parser.add_argument("--interactive", action="store_true", help="Run in interactive mode")
    parser.add_argument("--patient-id", type=str, default=USER_ID, help="Patient ID for the conversation")
    args = parser.parse_args()

    if args.demo:
        asyncio.run(run_conversation())
    elif args.interactive:
        asyncio.run(interactive_mode())
    else:
        # Default to demo mode if no arguments provided
        asyncio.run(run_conversation())
