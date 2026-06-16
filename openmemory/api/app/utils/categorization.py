import logging
import os
from typing import List

from app.utils.prompts import MEMORY_CATEGORIZATION_PROMPT
from dotenv import load_dotenv
from openai import OpenAI, OpenAIError
from pydantic import BaseModel
from tenacity import retry, stop_after_attempt, wait_exponential

load_dotenv()

# The OpenAI client is created lazily (see _get_openai_client): importing this
# module must NEVER require OpenAI credentials, otherwise the whole API crashes
# at startup in local-first installs that have no OPENAI_API_KEY.
_openai_client = None


def _is_local_only() -> bool:
    """True when the team fail-closed mode is active (``MEM0_LOCAL_ONLY``).

    Mirrors ``app.utils.memory.is_local_only``; kept inline so this lightweight
    module does not import the heavy memory module at app-startup import time.
    """
    return (os.environ.get("MEM0_LOCAL_ONLY") or "").strip().lower() in (
        "1", "true", "yes", "on",
    )


def _get_openai_client():
    """Lazily build the OpenAI client, or return ``None`` if unavailable.

    Returns ``None`` when no credentials are configured (e.g. local-first
    installs), so callers skip cloud categorization instead of crashing.
    """
    global _openai_client
    if _openai_client is None:
        try:
            _openai_client = OpenAI()
        except OpenAIError as e:
            logging.warning(f"[categorization] OpenAI client unavailable: {e}")
            return None
    return _openai_client


class MemoryCategories(BaseModel):
    categories: List[str]


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=15))
def get_categories_for_memory(memory: str) -> List[str]:
    # Auto-categorization uses OpenAI (cloud). In fail-closed local-only mode we
    # must not egress memory content, so categorization is skipped (no
    # categories) — the memory itself is still saved. Same when no client is
    # available (missing credentials).
    if _is_local_only():
        return []
    client = _get_openai_client()
    if client is None:
        return []

    try:
        messages = [
            {"role": "system", "content": MEMORY_CATEGORIZATION_PROMPT},
            {"role": "user", "content": memory}
        ]

        # Let OpenAI handle the pydantic parsing directly
        completion = client.beta.chat.completions.parse(
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
