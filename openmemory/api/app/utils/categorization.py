import logging
from typing import Dict, List

from app.utils.prompts import MEMORY_CATEGORIZATION_PROMPT
from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel
from tenacity import retry, stop_after_attempt, wait_exponential

load_dotenv()
openai_client = OpenAI()


class MemoryCategories(BaseModel):
    categories: List[str]


class BatchMemoryCategories(BaseModel):
    results: List[MemoryCategories]


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=15))
def get_categories_for_memories(memories: List[str]) -> Dict[str, List[str]]:
    """Categorize multiple memories in a single LLM call.

    Returns a dict mapping each memory string to its list of categories.
    Falls back to empty categories on failure so callers are never blocked.
    """
    if not memories:
        return {}

    numbered = "\n".join(f"{i + 1}. {m}" for i, m in enumerate(memories))
    prompt = (
        f"{MEMORY_CATEGORIZATION_PROMPT}\n\n"
        "You will receive a numbered list of memories. "
        "Return a JSON object with a 'results' key containing an array of objects, "
        "one per memory in the same order, each with a 'categories' key.\n\n"
        f"{numbered}"
    )

    try:
        completion = openai_client.beta.chat.completions.parse(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            response_format=BatchMemoryCategories,
            temperature=0,
        )
        parsed: BatchMemoryCategories = completion.choices[0].message.parsed
        return {
            memories[i]: [cat.strip().lower() for cat in item.categories]
            for i, item in enumerate(parsed.results)
            if i < len(memories)
        }
    except Exception as e:
        logging.error(f"[ERROR] Batch categorization failed: {e}")
        return {m: [] for m in memories}


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=15))
def get_categories_for_memory(memory: str) -> List[str]:
    try:
        messages = [
            {"role": "system", "content": MEMORY_CATEGORIZATION_PROMPT},
            {"role": "user", "content": memory}
        ]

        # Let OpenAI handle the pydantic parsing directly
        completion = openai_client.beta.chat.completions.parse(
            model="gpt-4o-mini",
            messages=messages,
            response_format=MemoryCategories,
            temperature=0
        )

        parsed: MemoryCategories = completion.choices[0].message.parsed
        return [cat.strip().lower() for cat in parsed.categories]

    except Exception as e:
        logging.error(f"[ERROR] Failed to get categories: {e}")
        try:
            logging.debug(f"[DEBUG] Raw response: {completion.choices[0].message.content}")
        except Exception as debug_e:
            logging.debug(f"[DEBUG] Could not extract raw response: {debug_e}")
        raise
