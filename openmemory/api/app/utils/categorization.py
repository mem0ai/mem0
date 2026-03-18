import json
import logging
import os
from typing import List

from app.utils.prompts import MEMORY_CATEGORIZATION_PROMPT
from dotenv import load_dotenv
from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

load_dotenv()
openai_client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url=os.getenv("OPENAI_BASE_URL"),
)

CATEGORY_MODEL = os.getenv("OPENMEMORY_CATEGORIZATION_MODEL") or os.getenv("OPENMEMORY_LLM_MODEL", "qwen3-max")


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=15))
def get_categories_for_memory(memory: str) -> List[str]:
    completion = None
    try:
        messages = [
            {"role": "system", "content": MEMORY_CATEGORIZATION_PROMPT},
            {"role": "system", "content": 'Respond with JSON only using this schema: {"categories": ["..."]}.'},
            {"role": "user", "content": memory}
        ]

        completion = openai_client.chat.completions.create(
            model=CATEGORY_MODEL,
            messages=messages,
            response_format={"type": "json_object"},
            temperature=0
        )

        payload = json.loads(completion.choices[0].message.content or "{}")
        categories = payload.get("categories", [])
        if not isinstance(categories, list):
            return []
        return [str(cat).strip().lower() for cat in categories if str(cat).strip()]

    except Exception as e:
        logging.error(f"[ERROR] Failed to get categories: {e}")
        if completion is not None:
            logging.debug(f"[DEBUG] Raw response: {completion.choices[0].message.content}")
        raise
