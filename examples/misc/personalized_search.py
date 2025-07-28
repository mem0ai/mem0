"""
Personalized Search Agent with Mem0 + Tavily
Uses LangChain agent pattern with Tavily tools for personalized search based on user memories stored in Mem0.
"""

from dotenv import load_dotenv
from mem0 import MemoryClient
from langchain.agents import create_openai_tools_agent, AgentExecutor
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI
from langchain_tavily import TavilySearch
from langchain.schema import HumanMessage
from datetime import datetime
import logging

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Initialize clients
mem0_client = MemoryClient()

# Set custom instructions to infer facts and memory to understand user preferences
mem0_client.project.update(
    custom_instructions='''
INFER THE MEMORIES FROM USER QUERIES EVEN IF IT'S A QUESTION.

We are building the personalized search for which we need to understand about user's preferences and life
and extract facts and memories out of it accordingly.

BE IT TIME, LOCATION, USER'S PERSONAL LIFE, CHOICES, USER'S PREFERENCES, we need to store those for better personalized search.
'''
)

llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.2)


def setup_user_history(user_id):
    """Simulate realistic user conversation history"""
    conversations = [
        [
            {"role": "user", "content": "What will be the weather today at Los Angeles? I need to go to pick up my daughter from office."},
            {"role": "assistant", "content": "I'll check the weather in LA for you, so that you can plan you daughter's pickup accordingly."}
        ],
        [
            {"role": "user", "content": "I'm looking for vegan restaurants in Santa Monica"},
            {"role": "assistant", "content": "I'll find great vegan options in Santa Monica."}
        ],
        [
            {"role": "user", "content": "My 7-year-old daughter is allergic to peanuts"},
            {"role": "assistant",
             "content": "I'll remember to check for peanut-free options in future recommendations."}
        ],
        [
            {"role": "user", "content": "I work remotely and need coffee shops with good wifi"},
            {"role": "assistant", "content": "I'll find remote-work-friendly coffee shops."}
        ],
        [
            {"role": "user", "content": "We love hiking and outdoor activities on weekends"},
            {"role": "assistant", "content": "Great! I'll keep your outdoor activity preferences in mind."}
        ]
    ]

    logger.info(f"Setting up user history for {user_id}")
    for conversation in conversations:
        mem0_client.add(conversation, user_id=user_id, output_format="v1.1")


def get_user_context(user_id, query):
    """Retrieve relevant user memories from Mem0"""
    try:

        filters = {
            "AND": [
                {"user_id": user_id}
            ]
        }
        user_memories = mem0_client.search(
            query=query,
            version="v2",
            filters=filters
        )

        if user_memories:
            context = "\n".join([f"- {memory['memory']}" for memory in user_memories])
            logger.info(f"Found {len(user_memories)} relevant memories for user {user_id}")
            return context
        else:
            logger.info(f"No relevant memories found for user {user_id}")
            return "No previous user context available."

    except Exception as e:
        logger.error(f"Error retrieving user context: {e}")
        return "Error retrieving user context."


def create_personalized_search_agent(user_context):
    """Create a LangChain agent for personalized search using Tavily"""

    # Create Tavily search tool
    tavily_search = TavilySearch(
        max_results=10,
        search_depth="advanced",
        include_answer=True,
        topic="general"
    )

    tools = [tavily_search]

    # Create personalized search prompt
    prompt = ChatPromptTemplate.from_messages([
        ("system", f"""You are a personalized search assistant. You help users find information that's relevant to their specific context and preferences.

USER CONTEXT AND PREFERENCES:
{user_context}

YOUR ROLE:
1. Analyze the user's query and their personal context/preferences above
2. Look for patterns in the context to understand their preferences, location, lifestyle, family situation, etc.
3. Create enhanced search queries that incorporate relevant personal context you discover
4. Use the tavily_search tool everytime with enhanced queries to find personalized results


INSTRUCTIONS:
- Study the user memories carefully to understand their situation
- If any questions ask something related to nearby, close to, etc. refer to previous user context for identifying locations and enhance search query based on that.
- If memories mention specific locations, consider them for local searches
- If memories reveal dietary preferences or restrictions, factor those in for food-related queries
- If memories show family context, consider family-friendly options
- If memories indicate work style or interests, incorporate those when relevant
- Use tavily_search tool everytime with enhanced queries (based on above context)
- Always explain which specific memories led you to personalize the search in certain ways

Do NOT assume anything not present in the user memories."""),

        MessagesPlaceholder(variable_name="messages"),
        MessagesPlaceholder(variable_name="agent_scratchpad"),
    ])

    # Create agent
    agent = create_openai_tools_agent(llm=llm, tools=tools, prompt=prompt)
    agent_executor = AgentExecutor(
        agent=agent,
        tools=tools,
        verbose=True,
        return_intermediate_steps=True
    )

    return agent_executor


def conduct_personalized_search(user_id, query):
    """
    Personalized search workflow using LangChain agent + Tavily + Mem0

    Returns search results with user personalization details
    """
    logger.info(f"Starting personalized search for user {user_id}: {query}")
    start_time = datetime.now()

    try:
        # Get user context from Mem0
        user_context = get_user_context(user_id, query)

        # Create personalized search agent
        agent_executor = create_personalized_search_agent(user_context)

        # Run the agent
        response = agent_executor.invoke({
            "messages": [HumanMessage(content=query)]
        })

        # Extract search details from intermediate steps
        search_queries_used = []
        total_results = 0

        for step in response.get("intermediate_steps", []):
            tool_call, tool_output = step
            if hasattr(tool_call, 'tool') and tool_call.tool == "tavily_search":
                search_query = tool_call.tool_input.get('query', '')
                search_queries_used.append(search_query)
                if isinstance(tool_output, dict) and 'results' in tool_output:
                    total_results += len(tool_output.get('results', []))

        # Store this search interaction in Mem0 for user preferences
        store_search_interaction(user_id, query, response['output'])

        # Compile results
        duration = (datetime.now() - start_time).total_seconds()

        results = {"agent_response": response['output']}

        logger.info(f"Personalized search completed in {duration:.2f}s")
        return results

    except Exception as e:
        logger.error(f"Error in personalized search workflow: {e}")
        return {"error": str(e)}


def store_search_interaction(user_id, original_query, agent_response):
    """Store search interaction in Mem0 for future personalization"""
    try:
        interaction = [
            {"role": "user", "content": f"Searched for: {original_query}"},
            {"role": "assistant", "content": f"Provided personalized results based on user preferences: {agent_response}"}
        ]

        mem0_client.add(messages=interaction, user_id=user_id, output_format="v1.1")

        logger.info(f"Stored search interaction for user {user_id}")

    except Exception as e:
        logger.error(f"Error storing search interaction: {e}")


def personalized_search_agent():
    """Example of the personalized search agent"""

    user_id = "john"

    # Setup user history
    print("\nSetting up user history from past conversations...")
    setup_user_history(user_id)   # This is one-time setup

    # Test personalized searches
    test_queries = [
        "good coffee shops nearby for working",
        "what can we gift our daughter for birthday? what's trending?"
    ]

    for i, query in enumerate(test_queries, 1):
        print(f"\n ----- {i}️⃣ PERSONALIZED SEARCH -----")
        print(f"Query: '{query}'")

        # Run personalized search
        results = conduct_personalized_search(user_id, query)

        if results.get("error"):
            print(f"Error: {results['error']}")

        else:
            print(f"Agent response: {results['agent_response']}")


if __name__ == "__main__":
    personalized_search_agent()
