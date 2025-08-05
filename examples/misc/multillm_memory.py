"""
Multi-LLM Research Team with Shared Knowledge Base

Use Case: AI Research Team where each model has different strengths:
- GPT-4: Technical analysis and code review
- Claude: Writing and documentation

All models share a common knowledge base, building on each other's work.
Example: GPT-4 analyzes a tech stack → Claude writes documentation →
Data analyst analyzes user data → All models can reference previous research.
"""

import logging

from dotenv import load_dotenv
from litellm import completion

from mem0 import MemoryClient

load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler("research_team.log")],
)
logger = logging.getLogger(__name__)


# Initialize memory client (platform version)
memory = MemoryClient()

# Research team models with specialized roles
RESEARCH_TEAM = {
    "tech_analyst": {
        "model": "gpt-4o",
        "role": "Technical Analyst - Code review, architecture, and technical decisions",
    },
    "writer": {
        "model": "claude-3-5-sonnet-20241022",
        "role": "Documentation Writer - Clear explanations and user guides",
    },
    "data_analyst": {
        "model": "gpt-4o-mini",
        "role": "Data Analyst - Insights, trends, and data-driven recommendations",
    },
}


def get_team_knowledge(topic: str, project_id: str) -> str:
    """Get relevant research from the team's shared knowledge base"""
    memories = memory.search(query=topic, user_id=project_id, limit=5)

    if memories:
        knowledge = "Team Knowledge Base:\n"
        for mem in memories:
            if "memory" in mem:
                # Get metadata to show which team member contributed
                metadata = mem.get("metadata", {})
                contributor = metadata.get("contributor", "Unknown")
                knowledge += f"• [{contributor}] {mem['memory']}\n"
        return knowledge
    return "Team Knowledge Base: Empty - starting fresh research"


def research_with_specialist(task: str, specialist: str, project_id: str) -> str:
    """Assign research task to specialist with access to team knowledge"""

    if specialist not in RESEARCH_TEAM:
        return f"Unknown specialist. Available: {list(RESEARCH_TEAM.keys())}"

    # Get team's accumulated knowledge
    team_knowledge = get_team_knowledge(task, project_id)

    # Specialist role and model
    spec_info = RESEARCH_TEAM[specialist]

    system_prompt = f"""You are the {spec_info['role']}.

{team_knowledge}

Build upon the team's existing research. Reference previous findings when relevant.
Provide actionable insights in your area of expertise."""

    # Call the specialist's model
    response = completion(
        model=spec_info["model"],
        messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": task}],
    )

    result = response.choices[0].message.content

    # Store research in shared knowledge base using both user_id and agent_id
    research_entry = [{"role": "user", "content": f"Task: {task}"}, {"role": "assistant", "content": result}]

    memory.add(
        research_entry,
        user_id=project_id,  # Project-level memory
        agent_id=specialist,  # Agent-specific memory
        metadata={"contributor": specialist, "task_type": "research", "model_used": spec_info["model"]},
        output_format="v1.1",
    )

    return result


def show_team_knowledge(project_id: str):
    """Display the team's accumulated research"""
    memories = memory.get_all(user_id=project_id)

    if not memories:
        logger.info("No research found for this project")
        return

    logger.info(f"Team Research Summary (Project: {project_id}):")

    # Group by contributor
    by_contributor = {}
    for mem in memories:
        if "metadata" in mem and mem["metadata"]:
            contributor = mem["metadata"].get("contributor", "Unknown")
            if contributor not in by_contributor:
                by_contributor[contributor] = []
            by_contributor[contributor].append(mem.get("memory", ""))

    for contributor, research_items in by_contributor.items():
        logger.info(f"{contributor.upper()}:")
        for i, item in enumerate(research_items[:3], 1):  # Show latest 3
            logger.info(f"   {i}. {item[:100]}...")


def demo_research_team():
    """Demo: Building a SaaS product with the research team"""

    project = "saas_product_research"

    # Define research pipeline
    research_pipeline = [
        {
            "stage": "Technical Architecture",
            "specialist": "tech_analyst",
            "task": "Analyze the best tech stack for a multi-tenant SaaS platform handling 10k+ users. Consider scalability, cost, and development speed.",
        },
        {
            "stage": "Product Documentation",
            "specialist": "writer",
            "task": "Based on the technical analysis, write a clear product overview and user onboarding guide for our SaaS platform.",
        },
        {
            "stage": "Market Analysis",
            "specialist": "data_analyst",
            "task": "Analyze market trends and pricing strategies for our SaaS platform. What metrics should we track?",
        },
        {
            "stage": "Strategic Decision",
            "specialist": "tech_analyst",
            "task": "Given our technical architecture, documentation, and market analysis - what should be our MVP feature priority?",
        },
    ]

    logger.info("AI Research Team: Building a SaaS Product")

    # Execute research pipeline
    for i, step in enumerate(research_pipeline, 1):
        logger.info(f"\nStage {i}: {step['stage']}")
        logger.info(f"Specialist: {step['specialist']}")

        result = research_with_specialist(step["task"], step["specialist"], project)
        logger.info(f"Task: {step['task']}")
        logger.info(f"Result: {result[:200]}...\n")

    show_team_knowledge(project)


if __name__ == "__main__":
    logger.info("Multi-LLM Research Team")
    demo_research_team()
