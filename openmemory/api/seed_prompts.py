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
                "description": "Manage memory operations (add, update, delete, no change)",
                "content": DEFAULT_UPDATE_MEMORY_PROMPT,
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
