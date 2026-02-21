import logging
import os
from typing import List, Optional

from app.utils.prompts import MEMORY_CATEGORIZATION_PROMPT
from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel
from tenacity import retry, stop_after_attempt, wait_exponential

load_dotenv()

# Lazy initialization - only create client when needed and if API key is available
_openai_client: Optional[OpenAI] = None


def get_openai_client() -> Optional[OpenAI]:
    """Get or initialize OpenAI client. Returns None if API key is not available."""
    global _openai_client
    
    if _openai_client is None:
        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            logging.warning("OPENAI_API_KEY not set. Memory categorization will be disabled.")
            return None
        
        try:
            _openai_client = OpenAI(api_key=api_key)
            logging.info("OpenAI client initialized successfully for categorization")
        except Exception as e:
            logging.error(f"Failed to initialize OpenAI client: {e}")
            return None
    
    return _openai_client


class MemoryCategories(BaseModel):
    categories: List[str]


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=15))
def get_categories_for_memory(memory: str) -> List[str]:
    """
    Get categories for a memory using OpenAI.
    
    Returns empty list if OpenAI client is not available (e.g., missing API key).
    """
    client = get_openai_client()
    if not client:
        logging.debug("OpenAI client not available, skipping categorization")
        return []
    
    try:
        messages = [
            {"role": "system", "content": MEMORY_CATEGORIZATION_PROMPT},
            {"role": "user", "content": memory}
        ]

        # Let OpenAI handle the pydantic parsing directly
        completion = client.beta.chat.completions.parse(
            model="gpt-4o-mini",
            messages=messages,
            response_format=MemoryCategories,
            temperature=0
        )

        parsed: MemoryCategories = completion.choices[0].message.parsed
        categories = [cat.strip().lower() for cat in parsed.categories]
        logging.debug(f"Categorized memory into: {categories}")
        return categories

    except Exception as e:
        logging.error(f"[ERROR] Failed to get categories: {e}")
        try:
            logging.debug(f"[DEBUG] Raw response: {completion.choices[0].message.content}")
        except Exception as debug_e:
            logging.debug(f"[DEBUG] Could not extract raw response: {debug_e}")
        # Return empty list instead of raising - categorization is optional
        return []
