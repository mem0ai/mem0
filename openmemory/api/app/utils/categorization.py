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

# Configure OpenAI API base URL for categorization.
# Prioritizes CATEGORIZATION_OPENAI_BASE_URL for custom endpoints (e.g., proxy services),
# falls back to general OPENAI_BASE_URL, then default OpenAI URL.
CATEGORIZATION_OPENAI_BASE_URL = os.environ.get(
    "CATEGORIZATION_OPENAI_BASE_URL", "https://api.openai.com/v1"
)
# Configure OpenAI API key for categorization.
# Prioritizes CATEGORIZATION_OPENAI_API_KEY, falls back to general OPENAI_API_KEY.
CATEGORIZATION_OPENAI_API_KEY = os.environ.get(
    "CATEGORIZATION_OPENAI_API_KEY",
    os.environ.get("OPENAI_API_KEY"),
)

CATEGORIZATION_OPENAI_MODEL = os.environ.get(
    "CATEGORIZATION_OPENAI_MODEL", "gpt-4o-mini"
)

# Initialize OpenAI client specifically for categorization.
openai_client = OpenAI(
    base_url=CATEGORIZATION_OPENAI_BASE_URL, api_key=CATEGORIZATION_OPENAI_API_KEY
)

print(f"✅ Categorization OpenAI Client initialized:")
print(f"   📍 Categorizatoin Base URL: {CATEGORIZATION_OPENAI_BASE_URL}")
print(f"   🤖 Categorizatoin Model: {CATEGORIZATION_OPENAI_MODEL}")
print(
    f"   🔑 Categorizatoin API Key: {'***' + CATEGORIZATION_OPENAI_API_KEY[-4:] if len(CATEGORIZATION_OPENAI_API_KEY) > 4 else '***'}"
)


class MemoryCategories(BaseModel):
    categories: List[str]


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=15))
def get_categories_for_memory(memory: str) -> List[str]:
    """Get categories for a memory."""
    try:
        response = openai_client.responses.parse(
            model=CATEGORIZATION_OPENAI_MODEL,
            instructions=MEMORY_CATEGORIZATION_PROMPT,
            input=memory,
            temperature=0,
            text_format=MemoryCategories,
        )
        response_json = json.loads(response.output[0].content[0].text)
        categories = response_json["categories"]
        categories = [cat.strip().lower() for cat in categories]
        # TODO: Validate categories later may be
        return categories
    except Exception as e:
        raise e
