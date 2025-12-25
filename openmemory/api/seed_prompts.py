"""Seed default prompts into the database."""
import sys
from pathlib import Path

# Add the parent directory to the Python path
sys.path.insert(0, str(Path(__file__).parent))

from datetime import datetime
from app.database import SessionLocal
from app.models import Prompt, PromptType
import sys
from pathlib import Path

# Add the mem0 submodule to the path to get the latest prompts
mem0_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(mem0_path))

from mem0.configs.prompts import (
    FACT_RETRIEVAL_PROMPT,
    USER_MEMORY_EXTRACTION_PROMPT,
    AGENT_MEMORY_EXTRACTION_PROMPT,
    DEFAULT_UPDATE_MEMORY_PROMPT,
    MEMORY_ANSWER_PROMPT,
    PROCEDURAL_MEMORY_SYSTEM_PROMPT
)
from app.utils.prompts import MEMORY_CATEGORIZATION_PROMPT

# Custom aggressive update memory prompt for better contradiction detection
CUSTOM_UPDATE_MEMORY_PROMPT = """You are a smart memory manager which controls the memory of a system. You can perform four operations: (1) ADD into the memory, (2) UPDATE the memory, (3) DELETE from the memory, and (4) NONE (no change).

CRITICAL RULES FOR DETECTING CONTRADICTIONS:

1. **Temporal Proximity Rule** (MOST IMPORTANT):
   - If two memories about the same topic were created within 10 minutes of each other, they are HIGHLY LIKELY to be corrections, clarifications, or mishearings
   - In these cases, be EXTREMELY AGGRESSIVE: DELETE the older fact and ADD the newer one
   - Examples:
     * Created 2 min apart: "going to X this summer" vs "going to X today" → DELETE old, ADD new
     * Created 5 min apart: "meeting with John" vs "meeting with Joan" → DELETE old, ADD new (likely misheard)
     * Created 1 min apart: "favorite color is blue" vs "favorite color is red" → DELETE old, ADD new (clarification)
     * Created 3 min apart: "allergic to peanuts" vs "not allergic to peanuts" → DELETE old, ADD new (correction)

2. **Temporal Contradictions**:
   - Different time/date for the same event or activity → DELETE old, ADD new
   - Example: "going to X this summer" vs "going to X today" → DELETE old, ADD new
   - Example: "meeting at 3pm" vs "meeting at 4pm" → DELETE old, ADD new

3. **Semantic Contradictions**:
   - Opposite preferences: "likes X" vs "dislikes X" → DELETE old, ADD new
   - Different attributes: "works at Company A" vs "works at Company B" → DELETE old, ADD new
   - Negations: "is vegetarian" vs "eats meat" → DELETE old, ADD new

4. **Singular Attribute Recognition** (CRITICAL):
   - Singular attributes can only have ONE value at a time:
     * "favorite X" / "favourite X" → Only ONE favorite allowed, DELETE all other favorites
     * "best X" → Only ONE best, DELETE other "best X" memories
     * "primary X" → Only ONE primary, DELETE other "primary X" memories
     * "main X" → Only ONE main, DELETE other "main X" memories
   - Examples:
     * "favorite color is blue" then "favorite color is red" → DELETE blue, ADD red
     * "best friend is Alice" then "best friend is Bob" → DELETE Alice, ADD Bob
     * "primary residence is NYC" then "primary residence is SF" → DELETE NYC, ADD SF
   - Note: "likes blue" and "likes red" are PLURAL (can like multiple things) - don't delete
   - Note: "favorite color is blue" is SINGULAR (only one favorite) - DELETE others

5. **UPDATE vs DELETE+ADD**:
   - Use UPDATE only when the new fact adds MORE DETAIL without changing core information
   - Use DELETE+ADD when the core information CHANGES (especially time, location, preferences)
   - When facts are created close together (< 10 min), prefer DELETE+ADD

6. **Default to Aggressive**:
   - When in doubt about contradictions, prefer DELETE+ADD over keeping duplicate information
   - Conversational corrections should ALWAYS trigger DELETE+ADD, not create duplicates

Operations:
- ADD: New information not present in existing memories
- UPDATE: Same core information with more detail (rare - prefer DELETE+ADD for changes)
- DELETE: Contradictory, outdated, or superseded information (especially if created recently)
- NONE: No change needed

Output Format: JSON array with objects containing {id, text, event, old_memory (optional)}

NOTE: You will receive the creation timestamp of existing memories. Use this to apply the Temporal Proximity Rule.
"""


def seed_prompts():
    """Seed the database with default prompts."""
    db = SessionLocal()

    try:
        # Define default prompts
        default_prompts = [
            {
                "prompt_type": PromptType.fact_retrieval,
                "display_name": "Fact Retrieval",
                "description": "Extract relevant facts from conversations",
                "content": FACT_RETRIEVAL_PROMPT,
            },
            {
                "prompt_type": PromptType.user_memory_extraction,
                "display_name": "User Memory Extraction",
                "description": "Extract user-specific memories and preferences from conversations",
                "content": USER_MEMORY_EXTRACTION_PROMPT,
            },
            {
                "prompt_type": PromptType.agent_memory_extraction,
                "display_name": "Agent Memory Extraction",
                "description": "Extract agent/assistant-specific memories and characteristics",
                "content": AGENT_MEMORY_EXTRACTION_PROMPT,
            },
            {
                "prompt_type": PromptType.update_memory,
                "display_name": "Update Memory",
                "description": "Manage memory operations (add, update, delete, no change) with aggressive contradiction detection",
                "content": CUSTOM_UPDATE_MEMORY_PROMPT,
            },
            {
                "prompt_type": PromptType.memory_answer,
                "display_name": "Memory Answer",
                "description": "Answer questions based on stored memories",
                "content": MEMORY_ANSWER_PROMPT,
            },
            {
                "prompt_type": PromptType.memory_categorization,
                "display_name": "Memory Categorization",
                "description": "Categorize memories into predefined or custom categories",
                "content": MEMORY_CATEGORIZATION_PROMPT,
            },
            {
                "prompt_type": PromptType.procedural_memory,
                "display_name": "Procedural Memory",
                "description": "Summarize procedural execution history",
                "content": PROCEDURAL_MEMORY_SYSTEM_PROMPT,
            },
        ]

        # Insert or update prompts
        for prompt_data in default_prompts:
            # Check if prompt already exists
            existing_prompt = db.query(Prompt).filter(
                Prompt.prompt_type == prompt_data["prompt_type"].value
            ).first()

            if existing_prompt:
                print(f"Prompt '{prompt_data['prompt_type'].value}' already exists, skipping...")
            else:
                prompt = Prompt(
                    prompt_type=prompt_data["prompt_type"].value,
                    display_name=prompt_data["display_name"],
                    description=prompt_data["description"],
                    content=prompt_data["content"],
                    is_active=True,
                    version=1,
                    created_at=datetime.now(),
                    updated_at=datetime.now(),
                )
                db.add(prompt)
                print(f"Added prompt: {prompt_data['display_name']}")

        db.commit()
        print("\nPrompt seeding completed successfully!")

    except Exception as e:
        db.rollback()
        print(f"Error seeding prompts: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_prompts()
