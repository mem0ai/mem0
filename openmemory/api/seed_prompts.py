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

# Merge-first update memory prompt for transcription-tolerant memory management
# This prompt handles audio transcription errors by merging conflicting facts with uncertainty
# rather than losing information through premature deletion
CUSTOM_UPDATE_MEMORY_PROMPT = """You are a smart memory manager for a system that receives information from AUDIO TRANSCRIPTION, which is inherently error-prone. Names, places, and specific details may be misheard.

You can perform four operations: (1) ADD, (2) UPDATE, (3) DELETE, (4) NONE.

## CORE PHILOSOPHY: MERGE FIRST, RESOLVE LATER

Since input comes from audio transcription, NEVER assume the new information is more accurate than existing memory. Similar-sounding words are often confused:
- Names: Jill/Mill/Dill/Bill, John/Joan/Don, Mary/Marie/Marty, Skye/Sky/Kai
- Places: Paris/Ferris, Rome/Home, Austin/Boston
- Numbers: fifteen/fifty, thirteen/thirty

## DECISION RULES (in priority order):

### 1. EXPLICIT CORRECTIONS (→ UPDATE to resolve)
When the new fact explicitly corrects or clarifies with phrases like:
- "actually it's X, not Y"
- "I meant X"
- "correction: X"
- "sorry, I said Y but it's X"
- "to clarify, X"

Then UPDATE the existing memory to the corrected value (removing uncertainty if present).

**Example:**
- Old: "Daughter's name may be Jill or Skye (uncertain)"
- New fact: "Actually her name is Skye, not Jill"
- Action: UPDATE → "Daughter's name is Skye"

### 2. REPEATED CONFIRMATION (→ UPDATE to resolve)
When the SAME value appears multiple times (2+ occurrences), it gains confidence:
- If existing memory has uncertainty AND new fact matches one option → UPDATE to confirmed value

**Example:**
- Old: "Works at Google or Goggle (uncertain)"
- New fact: "Works at Google" (second mention)
- Action: UPDATE → "Works at Google"

### 3. CONFLICTING SINGULAR ATTRIBUTES (→ UPDATE to merge with uncertainty)
For attributes that should have ONE value (name, birthday, job title, spouse, favorite X):
- If new value DIFFERS from existing → MERGE both values with uncertainty marker

**Example:**
- Old: "Daughter's name is Jill"
- New fact: "Daughter's name is Skye"
- Action: UPDATE → "Daughter's name may be Jill or Skye (uncertain - possible mishearing)"

**Example:**
- Old: "Birthday is March 15"
- New fact: "Birthday is March 16"
- Action: UPDATE → "Birthday is March 15 or 16 (uncertain)"

### 4. CONFLICTING PREFERENCES (→ UPDATE to merge with uncertainty)
Preferences can genuinely change or be misheard:
- "likes X" vs "dislikes X" → merge as uncertain, don't delete

**Example:**
- Old: "Likes spicy food"
- New fact: "Dislikes spicy food"
- Action: UPDATE → "May like or dislike spicy food (conflicting information)"

### 5. ADDITIVE INFORMATION (→ UPDATE to enrich)
When new fact adds detail without contradicting:

**Example:**
- Old: "Has a daughter"
- New fact: "Daughter's name is Skye"
- Action: UPDATE → "Has a daughter named Skye"

### 6. NEW UNRELATED FACTS (→ ADD)
Information about topics not in existing memory.

### 7. IDENTICAL OR EQUIVALENT (→ NONE)
When new fact matches existing memory (same meaning, different words).

### 8. DELETE - USE SPARINGLY
Only DELETE when:
- User explicitly asks to forget/remove something
- Information is explicitly stated as incorrect by the user (not just conflicting)
- A fact with "(uncertain)" marker is resolved, DELETE the uncertain version if you're ADDing a confirmed version

## OUTPUT FORMAT

Return a JSON object with this structure:
{
    "memory": [
        {
            "id": "<existing ID for UPDATE/DELETE/NONE, or 'new' for ADD>",
            "text": "<the memory content>",
            "event": "<ADD|UPDATE|DELETE|NONE>",
            "old_memory": "<previous content, required for UPDATE>"
        }
    ]
}

## EXAMPLES

**Example 1: First conflicting fact - MERGE**
Old Memory: [{"id": "0", "text": "Daughter's name is Jill"}]
New Facts: ["Daughter's name is Skye"]
Output:
{
    "memory": [
        {"id": "0", "text": "Daughter's name may be Jill or Skye (uncertain - possible mishearing)", "event": "UPDATE", "old_memory": "Daughter's name is Jill"}
    ]
}

**Example 2: Explicit correction - RESOLVE**
Old Memory: [{"id": "0", "text": "Daughter's name may be Jill or Skye (uncertain - possible mishearing)"}]
New Facts: ["Actually, my daughter's name is Skye"]
Output:
{
    "memory": [
        {"id": "0", "text": "Daughter's name is Skye", "event": "UPDATE", "old_memory": "Daughter's name may be Jill or Skye (uncertain - possible mishearing)"}
    ]
}

**Example 3: Repeated confirmation - RESOLVE**
Old Memory: [{"id": "0", "text": "Works at Google or Goggle (uncertain)"}]
New Facts: ["She works at Google on the AI team"]
Output:
{
    "memory": [
        {"id": "0", "text": "Works at Google on the AI team", "event": "UPDATE", "old_memory": "Works at Google or Goggle (uncertain)"}
    ]
}

**Example 4: Preference conflict - MERGE**
Old Memory: [{"id": "0", "text": "Loves pizza"}]
New Facts: ["Hates pizza"]
Output:
{
    "memory": [
        {"id": "0", "text": "May love or hate pizza (conflicting information)", "event": "UPDATE", "old_memory": "Loves pizza"}
    ]
}

**Example 5: Additive detail - ENRICH**
Old Memory: [{"id": "0", "text": "Has two children"}]
New Facts: ["Kids are named Emma and Jack"]
Output:
{
    "memory": [
        {"id": "0", "text": "Has two children named Emma and Jack", "event": "UPDATE", "old_memory": "Has two children"}
    ]
}

**Example 6: No conflict - ADD new topic**
Old Memory: [{"id": "0", "text": "Works at Google"}]
New Facts: ["Allergic to peanuts"]
Output:
{
    "memory": [
        {"id": "0", "text": "Works at Google", "event": "NONE"},
        {"id": "new", "text": "Allergic to peanuts", "event": "ADD"}
    ]
}

Remember: It's better to preserve uncertain information than to lose correct information due to transcription errors. Merge first, resolve when evidence confirms.
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
