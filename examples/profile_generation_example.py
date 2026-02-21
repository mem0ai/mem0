"""
Example: User Profile Generation with Mem0

This example demonstrates how to use Mem0's profile generation feature
to create evolving, compact user profiles that complement RAG-based memory retrieval.
"""

from mem0 import Memory

# Configuration with profile settings
config = {
    "llm": {"provider": "openai", "config": {"model": "gpt-4o-mini"}},
    "version": "v1.1",
    # Optional: Custom profile generation prompt
    "custom_profile_prompt": """
        Generate a concise user profile (200-400 tokens) covering:
        - Demographics and role
        - Communication preferences
        - Key expertise/skills
        - Major interests and preferences
        - Current goals/context
        Focus on stable, high-level traits, not specific events.
    """,
    # Profile auto-update configuration
    "profile_config": {
        "max_tokens": 400,  # Maximum profile length
        "auto_update": True,  # Enable automatic updates
        "async_update": True,  # Run updates in background (non-blocking)
        "memory_count": 10,  # Update after 10 new memories
        "time_elapsed": 86400,  # Update daily (24 hours in seconds)
    },
}

# Initialize Memory with profile configuration
m = Memory.from_config(config_dict=config)


def example_basic_usage():
    """Basic example of profile generation."""
    print("=== Basic Profile Generation ===\n")

    # Add some memories for user Alice
    m.add("My name is Alice and I'm a software engineer specializing in AI", user_id="alice")
    m.add("I prefer technical documentation over high-level overviews", user_id="alice")
    m.add("I'm currently working on a mental health AI assistant called MindMe", user_id="alice")
    m.add("I enjoy Python and have 5 years of experience with machine learning", user_id="alice")
    m.add("I prefer morning meetings and async communication", user_id="alice")

    # Get user profile - automatically generated from memories
    profile = m.get_profile(user_id="alice")

    print(f"User ID: {profile['user_id']}")
    print(f"Profile:\n{profile['profile']}")
    print(f"\nCreated at: {profile['created_at']}")
    print(f"Memory count at generation: {profile['memory_count_at_last_update']}")

    # New: Quality metrics
    if "quality_metrics" in profile:
        metrics = profile["quality_metrics"]
        print("\nQuality Metrics:")
        print(f"  - Confidence Score: {metrics['confidence_score']:.2f}")
        print(f"  - Memory Count: {metrics['memory_count']}")
        print(f"  - Token Count: {metrics['token_count']}")
        if metrics.get("warnings"):
            print(f"  - Warnings: {', '.join(metrics['warnings'])}")

    print("\n" + "=" * 50 + "\n")


def example_profile_in_session_context():
    """Example of using profile as session context for AI interactions."""
    print("=== Using Profile in Session Context ===\n")

    # Add more memories
    m.add("I have diabetes and take medication in the morning", user_id="bob")
    m.add("I prefer appointments after 2 PM", user_id="bob")
    m.add("I'm anxious about needles", user_id="bob")
    m.add("I'm trying to lose weight and prefer plant-based diets", user_id="bob")

    # Get profile for session context
    profile = m.get_profile(user_id="bob")

    # Search for specific memories
    user_message = "I need to schedule a blood test"
    relevant_memories = m.search(query=user_message, user_id="bob", limit=3)

    # Construct AI session prompt with both profile and relevant memories
    system_prompt = f"""You are a healthcare AI assistant.

User Profile:
{profile["profile"]}

Relevant Memories:
{chr(10).join(f"- {mem['memory']}" for mem in relevant_memories["results"])}

Provide personalized assistance based on the user's profile and memories."""

    print("System Prompt for AI:")
    print(system_prompt)
    print("\n" + "=" * 50 + "\n")


def example_auto_update():
    """Example demonstrating profile auto-update."""
    print("=== Profile Auto-Update ===\n")

    # Initial profile
    m.add("My name is Carol and I work as a data scientist", user_id="carol")
    profile1 = m.get_profile(user_id="carol")
    print(f"Initial profile:\n{profile1['profile']}\n")
    print(f"Memory count: {profile1['memory_count_at_last_update']}\n")

    # Add more memories to trigger auto-update (threshold is 10 new memories)
    for i in range(10):
        m.add(
            f"Carol's interest #{i}: {['deep learning', 'NLP', 'computer vision', 'MLOps', 'data visualization', 'statistics', 'Python', 'SQL', 'cloud computing', 'model deployment'][i]}",
            user_id="carol",
        )

    # Profile should have auto-updated after 10 new memories
    profile2 = m.get_profile(user_id="carol")
    print(f"Updated profile (after 10 new memories):\n{profile2['profile']}\n")
    print(f"Memory count: {profile2['memory_count_at_last_update']}\n")
    print(f"Updated at: {profile2['updated_at']}")
    print("\n" + "=" * 50 + "\n")


def example_custom_domain():
    """Example with custom profile prompt for specific domain."""
    print("=== Custom Domain Profile (Customer Support) ===\n")

    # Configure for customer support domain
    support_config = {
        "llm": {"provider": "openai", "config": {"model": "gpt-4o-mini"}},
        "version": "v1.1",
        "custom_profile_prompt": """
            Generate a customer support profile (200-400 tokens) including:
            - Customer tier/status (premium, standard, etc.)
            - Communication style preference
            - Technical proficiency level
            - Common issues and preferences
            - Timezone and availability preferences
            Focus on information relevant for support interactions.
        """,
        "profile_config": {
            "max_tokens": 400,
            "auto_update": True,
            "memory_count": 5,
            "time_elapsed": 86400,
        },
    }

    m_support = Memory.from_config(config_dict=support_config)

    # Add customer support memories
    m_support.add("Customer is a premium tier subscriber", user_id="customer_123")
    m_support.add("Prefers detailed technical explanations", user_id="customer_123")
    m_support.add("Located in PST timezone", user_id="customer_123")
    m_support.add("Previously had billing issues that were resolved", user_id="customer_123")
    m_support.add("Highly technical, works as a DevOps engineer", user_id="customer_123")

    # Get customer profile
    profile = m_support.get_profile(user_id="customer_123")

    print(f"Customer Profile:\n{profile['profile']}")
    print("\n" + "=" * 50 + "\n")


def example_profile_vs_search():
    """Example comparing profile (semantic) vs search (episodic) memory."""
    print("=== Profile (Semantic) vs Search (Episodic) ===\n")

    # Add various memories
    user_id = "dave"
    memories = [
        "Dave is a product manager at a tech startup",
        "Yesterday, Dave had a meeting with the design team",
        "Dave prefers visual presentations over text-heavy documents",
        "Last week, Dave launched a new feature for mobile users",
        "Dave's current goal is to increase user engagement by 20%",
        "Dave likes to brainstorm in the morning",
        "Dave attended a conference on product-led growth in March",
        "Dave values data-driven decision making",
    ]

    for memory in memories:
        m.add(memory, user_id=user_id)

    # Get profile (semantic - "who is Dave?")
    profile = m.get_profile(user_id=user_id)
    print("SEMANTIC MEMORY (Profile - who is Dave?):")
    print(profile["profile"])
    print("\n")

    # Search for specific event (episodic - "what happened?")
    query = "What did Dave do last week?"
    search_results = m.search(query=query, user_id=user_id, limit=3)
    print("EPISODIC MEMORY (Search - what happened?):")
    for result in search_results["results"]:
        print(f"- {result['memory']} (score: {result.get('score', 'N/A')})")

    print("\n")
    print("KEY INSIGHT:")
    print("Profile provides stable semantic understanding ('Dave is a product manager who values data')")
    print("Search provides specific episodic events ('Dave launched a feature last week')")
    print("Using both together creates comprehensive context for AI interactions!")
    print("\n" + "=" * 50 + "\n")


def example_profile_history():
    """Example demonstrating profile versioning and history tracking."""
    print("=== Profile History & Versioning ===\n")

    user_id = "eve"

    # Create initial profile
    m.add("Eve is a UX designer", user_id=user_id)
    m.add("She specializes in mobile interfaces", user_id=user_id)
    profile_v1 = m.get_profile(user_id=user_id)
    print(f"Initial Profile (v1):\n{profile_v1['profile']}\n")

    # Add more memories and manually update profile
    m.add("Eve recently moved into management role", user_id=user_id)
    m.add("She now leads a team of 5 designers", user_id=user_id)
    m.update_profile(user_id=user_id, force=True)  # Manual update

    profile_v2 = m.get_profile(user_id=user_id)
    print(f"Updated Profile (v2):\n{profile_v2['profile']}\n")

    # View profile history
    history = m.get_profile_history(user_id=user_id, limit=5)
    print(f"Profile History ({len(history)} versions):")
    for version in history:
        print(f"\n  Version {version['version']}:")
        print(f"    Created: {version['created_at']}")
        print(f"    Update Reason: {version['update_reason']}")
        print(f"    Memory Count: {version['memory_count']}")
        print(f"    Profile: {version['profile'][:100]}...")

    print("\n" + "=" * 50 + "\n")


def example_manual_updates():
    """Example demonstrating manual profile updates."""
    print("=== Manual Profile Updates ===\n")

    user_id = "frank"

    # Add some memories
    m.add("Frank is a sales executive", user_id=user_id)
    m.add("He works in B2B software", user_id=user_id)

    profile = m.get_profile(user_id=user_id)
    print(f"Initial Profile:\n{profile['profile']}\n")

    # Add critical information and force immediate update
    m.add("Frank just closed a $1M deal with a Fortune 500 company", user_id=user_id)
    m.add("He was promoted to VP of Sales", user_id=user_id)

    # Force immediate update (don't wait for auto-update thresholds)
    updated_profile = m.update_profile(user_id=user_id, force=True)
    print(f"Manually Updated Profile:\n{updated_profile['profile']}\n")

    print("Use update_profile(force=True) when you need immediate profile refresh")
    print("after significant events or milestones!")
    print("\n" + "=" * 50 + "\n")


if __name__ == "__main__":
    # Run examples
    print("\n" + "=" * 50)
    print("MEM0 PROFILE GENERATION EXAMPLES")
    print("=" * 50 + "\n")

    example_basic_usage()
    example_profile_in_session_context()
    example_auto_update()
    example_custom_domain()
    example_profile_vs_search()
    example_profile_history()
    example_manual_updates()

    print("Examples completed!")
