import json
import logging
from typing import List

from app.utils.prompts import MEMORY_CATEGORIZATION_PROMPT
from pydantic import BaseModel
from tenacity import retry, stop_after_attempt, wait_exponential


class MemoryCategories(BaseModel):
    categories: List[str]


def _get_llm():
    """Get the configured LLM instance from the memory client."""
    from app.utils.memory import get_memory_client

    client = get_memory_client()
    if client is None:
        raise RuntimeError("Memory client is not initialized. Cannot categorize memories.")
    return client.llm


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=15))
def get_categories_for_memory(memory: str) -> List[str]:
    try:
        llm = _get_llm()

        messages = [
            {"role": "system", "content": MEMORY_CATEGORIZATION_PROMPT},
            {"role": "user", "content": memory},
        ]

        response = llm.generate_response(
            messages=messages,
            response_format={"type": "json_object"},
        )

        parsed = MemoryCategories(**json.loads(response))
        return [cat.strip().lower() for cat in parsed.categories]

    except Exception as e:
        logging.error(f"[ERROR] Failed to get categories: {e}")
        raise
