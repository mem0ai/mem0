from agents import Agent, Runner, enable_verbose_stdout_logging, function_tool
from dotenv import load_dotenv

from mem0 import MemoryClient

enable_verbose_stdout_logging()

load_dotenv()

# Initialize Mem0 client
mem0 = MemoryClient()


# Define memory tools for the agent
@function_tool
def search_memory(query: str, user_id: str) -> str:
    """Search through past conversations and memories"""
    memories = mem0.search(query, user_id=user_id, limit=3)
    if memories:
        return "\n".join([f"- {mem['memory']}" for mem in memories])
    return "No relevant memories found."


@function_tool
def save_memory(content: str, user_id: str) -> str:
    """Save important information to memory"""
    mem0.add([{"role": "user", "content": content}], user_id=user_id)
    return "Information saved to memory."


# Specialized agents
travel_agent = Agent(
    name="Travel Planner",
    instructions="""You are a travel planning specialist. Use get_user_context to
    understand the user's travel preferences and history before making recommendations.
    After providing your response, use store_conversation to save important details.""",
    tools=[search_memory, save_memory],
    model="gpt-4o",
)

health_agent = Agent(
    name="Health Advisor",
    instructions="""You are a health and wellness advisor. Use get_user_context to
    understand the user's health goals and dietary preferences.
    After providing advice, use store_conversation to save relevant information.""",
    tools=[search_memory, save_memory],
    model="gpt-4o",
)

# Triage agent with handoffs
triage_agent = Agent(
    name="Personal Assistant",
    instructions="""You are a helpful personal assistant that routes requests to specialists.
    For travel-related questions (trips, hotels, flights, destinations), hand off to Travel Planner.
    For health-related questions (fitness, diet, wellness, exercise), hand off to Health Advisor.
    For general questions, you can handle them directly using available tools.""",
    handoffs=[travel_agent, health_agent],
    model="gpt-4o",
)


def chat_with_handoffs(user_input: str, user_id: str) -> str:
    """
    Handle user input with automatic agent handoffs and memory integration.

    Args:
        user_input: The user's message
        user_id: Unique identifier for the user

    Returns:
        The agent's response
    """
    # Run the triage agent (it will automatically handoffs when needed)
    result = Runner.run_sync(triage_agent, user_input)

    # Store the original conversation in memory
    conversation = [{"role": "user", "content": user_input}, {"role": "assistant", "content": result.final_output}]
    mem0.add(conversation, user_id=user_id)

    return result.final_output


# Example usage
# response = chat_with_handoffs("Which places should I vist?", user_id="alex")
# print(response)
