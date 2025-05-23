import json
import logging
import os
from openai import OpenAI
from typing import List
from dotenv import load_dotenv
from pydantic import BaseModel
from tenacity import retry, stop_after_attempt, wait_exponential
from app.utils.prompts import MEMORY_CATEGORIZATION_PROMPT

load_dotenv()

class MemoryCategories(BaseModel):
    categories: List[str]

def get_openai_client():
    """Initializes and returns an OpenAI client, ensuring API key is loaded."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        # This error will now be more specific if the key is missing during actual use
        logging.error("OPENAI_API_KEY environment variable not found for OpenAI client.")
        raise ValueError("OPENAI_API_KEY environment variable not found.")
    return OpenAI(api_key=api_key)

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=15))
def get_categories_for_memory(memory: str) -> List[str]:
    """Get categories for a memory."""
    openai_client = get_openai_client()
    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": MEMORY_CATEGORIZATION_PROMPT},
                {"role": "user", "content": memory}
            ],
            response_format={ "type": "json_object" },
            temperature=0,
        )
        response_data = json.loads(response.choices[0].message.content)
        categories = response_data.get('categories', [])
        categories = [cat.strip().lower() for cat in categories if isinstance(cat, str)]
        return categories
    except Exception as e:
        logging.error(f"Error categorizing memory: {e}", exc_info=True)
        raise e
