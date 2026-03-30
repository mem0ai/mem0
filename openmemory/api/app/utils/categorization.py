import json
import logging
from typing import List

from app.utils.prompts import MEMORY_CATEGORIZATION_PROMPT
from pydantic import BaseModel
from tenacity import retry, stop_after_attempt, wait_exponential


class MemoryCategories(BaseModel):
    categories: List[str]


class BatchMemoryCategories(BaseModel):
    results: List[MemoryCategories]


def _get_llm():
    """Get the configured LLM instance from the memory client."""
    from app.utils.memory import get_memory_client

    client = get_memory_client()
    if client is None:
        raise RuntimeError("Memory client is not initialized. Cannot categorize memories.")
    return client.llm


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=15))
def get_categories_for_memories(memories: List[str]) -> List[List[str]]:
    """Categorize multiple memories in a single LLM call.

    Returns a list of category lists in this data type: MemoryCategories, one per memory in the same order.
    Falls back to empty categories on failure so callers are never blocked.
    """
    if not memories:
        return []

    llm = _get_llm()

    numbered = "\n".join(f"{i + 1}. {m}" for i, m in enumerate(memories))
    prompt = (
        f"{MEMORY_CATEGORIZATION_PROMPT}\n\n"
        "You will receive a numbered list of memories. "
        "Return a JSON object with a 'results' key containing an array of objects, "
        "one per memory in the same order, each with a 'categories' key.\n\n"
        f"{numbered}"
    )

    try:
        response = llm.generate_response(
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
        )
        parsed = BatchMemoryCategories(**json.loads(response))
        return [
            [cat.strip().lower() for cat in item.categories]
            for item in parsed.results[: len(memories)]
        ]
    except Exception as e:
        logging.error(f"[ERROR] Batch categorization failed: {e}")
        return [[] for _ in memories]


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
