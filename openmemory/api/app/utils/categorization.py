import logging
import os
from typing import List

from app.utils.prompts import MEMORY_CATEGORIZATION_PROMPT
from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel
from tenacity import retry, stop_after_attempt, wait_exponential

load_dotenv()
_base_url = os.getenv("OPENAI_BASE_URL") or os.getenv("LLM_BASE_URL")
openai_client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY") or os.getenv("LLM_API_KEY"),
    base_url=_base_url or None,
)
categorization_model = os.getenv("OPENMEMORY_CATEGORIZATION_MODEL", "gpt-4o-mini")
categorization_disabled = os.getenv("OPENMEMORY_DISABLE_CATEGORIZATION", "").lower() in {"1", "true", "yes", "on"}
logger = logging.getLogger(__name__)


class MemoryCategories(BaseModel):
    categories: List[str]


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=15))
def get_categories_for_memory(memory: str) -> List[str]:
    if categorization_disabled:
        return []

    try:
        messages = [
            {"role": "system", "content": MEMORY_CATEGORIZATION_PROMPT},
            {"role": "user", "content": memory}
        ]

        # Let OpenAI handle the pydantic parsing directly
        completion = openai_client.beta.chat.completions.parse(
            model=categorization_model,
            messages=messages,
            response_format=MemoryCategories,
            temperature=0
        )

        parsed: MemoryCategories = completion.choices[0].message.parsed
        return [cat.strip().lower() for cat in parsed.categories]

    except Exception as e:
        logger.warning("Failed to categorize memory; continuing without categories: %s", e)
        try:
            logger.debug(f"[DEBUG] Raw response: {completion.choices[0].message.content}")
        except Exception as debug_e:
            logger.debug(f"[DEBUG] Could not extract raw response: {debug_e}")
        return []
