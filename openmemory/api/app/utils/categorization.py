import json
import logging
import os
from typing import List

from app.utils.prompts import MEMORY_CATEGORIZATION_PROMPT
from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel, ValidationError
from tenacity import retry, stop_after_attempt, wait_exponential

load_dotenv()

# Prefer DEEPSEEK_API_KEY over OPENAI_API_KEY so categorization works without a real
# OpenAI key. DeepSeek's API is OpenAI-compatible.
_deepseek_key = os.getenv("DEEPSEEK_API_KEY")
if _deepseek_key:
    openai_client = OpenAI(
        api_key=_deepseek_key,
        base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1"),
    )
    _CATEGORIZATION_MODEL = "deepseek-chat"
    _USE_STRUCTURED_OUTPUT = False  # DeepSeek doesn't support beta parse yet
else:
    openai_client = OpenAI()
    _CATEGORIZATION_MODEL = "gpt-4o-mini"
    _USE_STRUCTURED_OUTPUT = True


class MemoryCategories(BaseModel):
    categories: List[str]


_JSON_INSTRUCTION = (
    "\n\nReturn ONLY a compact JSON object with this exact shape and no extra text:\n"
    '{"categories": ["<category-1>", "<category-2>"]}'
)


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=15))
def get_categories_for_memory(memory: str) -> List[str]:
    completion = None
    try:
        if _USE_STRUCTURED_OUTPUT:
            messages = [
                {"role": "system", "content": MEMORY_CATEGORIZATION_PROMPT},
                {"role": "user", "content": memory},
            ]
            completion = openai_client.beta.chat.completions.parse(
                model=_CATEGORIZATION_MODEL,
                messages=messages,
                response_format=MemoryCategories,
                temperature=0,
            )
            parsed: MemoryCategories = completion.choices[0].message.parsed
            return [cat.strip().lower() for cat in parsed.categories]

        # DeepSeek path: use JSON mode + manual parse.
        messages = [
            {
                "role": "system",
                "content": MEMORY_CATEGORIZATION_PROMPT + _JSON_INSTRUCTION,
            },
            {"role": "user", "content": memory},
        ]
        completion = openai_client.chat.completions.create(
            model=_CATEGORIZATION_MODEL,
            messages=messages,
            response_format={"type": "json_object"},
            temperature=0,
        )
        raw = completion.choices[0].message.content or "{}"
        data = json.loads(raw)
        parsed = MemoryCategories(**data)
        return [cat.strip().lower() for cat in parsed.categories]

    except (json.JSONDecodeError, ValidationError) as e:
        logging.error(f"[ERROR] Failed to parse categorization response: {e}")
        try:
            logging.debug(
                f"[DEBUG] Raw response: {completion.choices[0].message.content}"
            )
        except Exception as debug_e:
            logging.debug(f"[DEBUG] Could not extract raw response: {debug_e}")
        raise
    except Exception as e:
        logging.error(f"[ERROR] Failed to get categories: {e}")
        try:
            logging.debug(
                f"[DEBUG] Raw response: {completion.choices[0].message.content}"
            )
        except Exception as debug_e:
            logging.debug(f"[DEBUG] Could not extract raw response: {debug_e}")
        raise
