import logging
from typing import List

from app.utils.prompts import MEMORY_CATEGORIZATION_PROMPT
from dotenv import load_dotenv
from pydantic import BaseModel
from tenacity import retry, stop_after_attempt, wait_exponential

load_dotenv()


class MemoryCategories(BaseModel):
    categories: List[str]


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=15))
def get_categories_for_memory(memory: str) -> List[str]:
    try:
        # Import here to avoid circular import
        from app.utils.memory import get_memory_client
        
        # Get the memory client to access LLM configuration
        memory_client = get_memory_client()
        if not memory_client or not hasattr(memory_client, 'llm'):
            logging.warning("[WARNING] Memory client or LLM not available, skipping categorization")
            return []

        messages = [
            {"role": "system", "content": MEMORY_CATEGORIZATION_PROMPT},
            {"role": "user", "content": memory}
        ]

        # Use the memory client's LLM for categorization
        # Since we can't use structured output with non-OpenAI models,
        # we'll get the raw response and parse it manually
        response = memory_client.llm.generate_response(messages, temperature=0)
        
        # Simple parsing for category list from response
        # Expected format: categories separated by commas or newlines
        categories = []
        for line in response.split('\n'):
            line = line.strip()
            if line and not line.startswith('#') and not line.startswith('-'):
                # Split by comma if multiple categories in one line
                line_categories = [cat.strip().lower() for cat in line.split(',') if cat.strip()]
                categories.extend(line_categories)
        
        return categories[:10]  # Limit to 10 categories max

    except Exception as e:
        logging.error(f"[ERROR] Failed to get categories: {e}")
        # Return empty list instead of raising to prevent blocking memory operations
        return []
