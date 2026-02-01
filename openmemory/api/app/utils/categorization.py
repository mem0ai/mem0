"""Memory categorization using OpenAI.

Environment variables:
- CATEGORIZATION_MODEL: Model to use (default: gpt-4o-mini)
  Supports both GPT-4 and GPT-5 models automatically.
- CATEGORIZATION_PROMPT: Prompt style - "general" or "developer" (default: general)
"""

import logging
import os
from typing import List

from app.utils.prompts import (
    DEVELOPER_CATEGORIZATION_PROMPT,
    GENERAL_CATEGORIZATION_PROMPT,
)
from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel
from tenacity import retry, stop_after_attempt, wait_exponential

load_dotenv()
openai_client = OpenAI()


class MemoryCategories(BaseModel):
    categories: List[str]


def _get_prompt() -> str:
    """Get categorization prompt based on CATEGORIZATION_PROMPT env variable."""
    prompt_type = os.getenv("CATEGORIZATION_PROMPT", "general").lower()
    if prompt_type == "developer":
        return DEVELOPER_CATEGORIZATION_PROMPT
    return GENERAL_CATEGORIZATION_PROMPT


def _get_model() -> str:
    """Get model from CATEGORIZATION_MODEL env variable."""
    return os.getenv("CATEGORIZATION_MODEL", "gpt-4o-mini")


def _is_gpt5_model(model: str) -> bool:
    """Check if model is GPT-5 family (requires Responses API)."""
    return model.startswith("gpt-5")


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=15))
def get_categories_for_memory(memory: str) -> List[str]:
    """Categorize a memory using OpenAI.

    Automatically uses the appropriate API based on model:
    - GPT-5 models: Responses API (no temperature support)
    - GPT-4 models: Chat Completions API
    """
    try:
        model = _get_model()
        prompt = _get_prompt()
        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": memory}
        ]

        if _is_gpt5_model(model):
            # GPT-5: Use Responses API (no temperature parameter)
            response = openai_client.responses.parse(
                model=model,
                input=messages,
                text_format=MemoryCategories,
            )
            parsed: MemoryCategories = response.output_parsed
        else:
            # GPT-4: Use Chat Completions API
            completion = openai_client.beta.chat.completions.parse(
                model=model,
                messages=messages,
                response_format=MemoryCategories,
                temperature=0
            )
            parsed: MemoryCategories = completion.choices[0].message.parsed

        return [cat.strip().lower() for cat in parsed.categories]

    except Exception as e:
        logging.error(f"[ERROR] Failed to get categories: {e}")
        raise
