import logging
import json
import os
from typing import List

from app.utils.prompts import MEMORY_CATEGORIZATION_PROMPT
from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel
from tenacity import retry, stop_after_attempt, wait_exponential

load_dotenv()


def _build_openai_client() -> OpenAI:
    kwargs = {}
    api_key = os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY")
    base_url = os.getenv("LLM_BASE_URL") or os.getenv("OPENAI_BASE_URL")

    if api_key:
        kwargs["api_key"] = api_key
    if base_url:
        kwargs["base_url"] = base_url

    return OpenAI(**kwargs)


openai_client = _build_openai_client()
categorization_model = os.getenv("LLM_MODEL", "gpt-4o-mini")


class MemoryCategories(BaseModel):
    categories: List[str]


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=15))
def get_categories_for_memory(memory: str) -> List[str]:
    try:
        messages = [
            {"role": "system", "content": MEMORY_CATEGORIZATION_PROMPT},
            {"role": "user", "content": memory}
        ]

        try:
            # Let OpenAI handle the pydantic parsing directly when available.
            completion = openai_client.beta.chat.completions.parse(
                model=categorization_model,
                messages=messages,
                response_format=MemoryCategories,
                temperature=0
            )

            parsed: MemoryCategories = completion.choices[0].message.parsed
        except Exception:
            completion = openai_client.chat.completions.create(
                model=categorization_model,
                messages=messages,
                response_format={"type": "json_object"},
                temperature=0
            )
            content = completion.choices[0].message.content or "{}"
            try:
                parsed = MemoryCategories.model_validate(json.loads(content))
            except json.JSONDecodeError:
                start = content.find("{")
                end = content.rfind("}")
                if start == -1 or end == -1 or end <= start:
                    logging.warning("[WARN] Category response was not JSON; storing memory without categories")
                    return []
                parsed = MemoryCategories.model_validate(json.loads(content[start:end + 1]))
        return [cat.strip().lower() for cat in parsed.categories]

    except Exception as e:
        logging.warning(f"[WARN] Failed to get categories; storing memory without categories: {e}")
        try:
            logging.debug(f"[DEBUG] Raw response: {completion.choices[0].message.content}")
        except Exception as debug_e:
            logging.debug(f"[DEBUG] Could not extract raw response: {debug_e}")
        return []
