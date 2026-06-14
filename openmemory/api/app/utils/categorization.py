"""
Memory categorization, run off the request path.

Categorization makes one LLM call per memory write. Previously it ran *inside*
the SQLAlchemy flush via ``after_insert``/``after_update`` events, which:
  - blocked every add/search write on a cross-network LLM round-trip (with up to
    3 retries), and
  - re-categorized on every state change (delete/archive/pause), wasting calls.

Now writes only enqueue work via :func:`schedule_categorization`, which runs the
LLM call + DB upsert in a background thread with its own session, after the
caller has committed. The provider is configurable (defaults to OpenAI) and the
client is created lazily so importing this module never requires an API key.

Disable entirely with ``OPENMEMORY_DISABLE_CATEGORIZATION=true`` (e.g. for bulk
migrations that would exhaust an LLM quota).
"""

import logging
import os
from concurrent.futures import ThreadPoolExecutor
from typing import List
from uuid import UUID

from app.utils.prompts import MEMORY_CATEGORIZATION_PROMPT
from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel
from tenacity import retry, stop_after_attempt, wait_exponential

load_dotenv()

logger = logging.getLogger(__name__)

_CATEGORIZATION_DISABLED = os.environ.get("OPENMEMORY_DISABLE_CATEGORIZATION", "false").lower() == "true"
# Categorization LLM is independent of the memory LLM provider. Defaults to
# OpenAI but supports any OpenAI-compatible endpoint via base_url.
_MODEL = os.environ.get("CATEGORIZATION_MODEL", "gpt-4o-mini")
_MAX_WORKERS = int(os.environ.get("OPENMEMORY_CATEGORIZATION_WORKERS", "4"))

_executor = ThreadPoolExecutor(max_workers=_MAX_WORKERS, thread_name_prefix="categorize")
_openai_client = None


class MemoryCategories(BaseModel):
    categories: List[str]


def _get_client() -> OpenAI:
    """Lazily build the categorization LLM client (OpenAI-compatible)."""
    global _openai_client
    if _openai_client is None:
        api_key = os.environ.get("CATEGORIZATION_API_KEY") or os.environ.get("OPENAI_API_KEY")
        base_url = os.environ.get("CATEGORIZATION_BASE_URL") or os.environ.get("OPENAI_BASE_URL")
        kwargs = {}
        if api_key:
            kwargs["api_key"] = api_key
        if base_url:
            kwargs["base_url"] = base_url
        _openai_client = OpenAI(**kwargs)
    return _openai_client


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=15))
def get_categories_for_memory(memory: str) -> List[str]:
    try:
        messages = [
            {"role": "system", "content": MEMORY_CATEGORIZATION_PROMPT},
            {"role": "user", "content": memory},
        ]

        completion = _get_client().beta.chat.completions.parse(
            model=_MODEL,
            messages=messages,
            response_format=MemoryCategories,
            temperature=0,
        )

        parsed: MemoryCategories = completion.choices[0].message.parsed
        return [cat.strip().lower() for cat in parsed.categories]

    except Exception as e:
        logger.error(f"[ERROR] Failed to get categories: {e}")
        raise


def _apply_categories(memory_id: UUID, content: str) -> None:
    """Compute categories for a memory and persist the associations.

    Runs in a background thread with its own DB session. Imports models lazily to
    avoid a circular import (models imports this module).
    """
    # Imported here, not at module top, to break the import cycle.
    from app.database import SessionLocal
    from app.models import Category, Memory, memory_categories

    db = SessionLocal()
    try:
        categories = get_categories_for_memory(content)
        for category_name in categories:
            category = db.query(Category).filter(Category.name == category_name).first()
            if not category:
                category = Category(
                    name=category_name,
                    description=f"Automatically created category for {category_name}",
                )
                db.add(category)
                db.flush()

            existing = db.execute(
                memory_categories.select().where(
                    (memory_categories.c.memory_id == memory_id)
                    & (memory_categories.c.category_id == category.id)
                )
            ).first()

            if not existing:
                # Guard against the memory having been hard-deleted before this
                # background job ran.
                if db.query(Memory).filter(Memory.id == memory_id).first() is None:
                    db.rollback()
                    return
                db.execute(
                    memory_categories.insert().values(
                        memory_id=memory_id,
                        category_id=category.id,
                    )
                )
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Error categorizing memory {memory_id}: {e}")
    finally:
        db.close()


def schedule_categorization(memory_id: UUID, content: str) -> None:
    """Enqueue categorization of a memory. No-op when disabled. Never raises."""
    if _CATEGORIZATION_DISABLED or not content:
        return
    try:
        _executor.submit(_apply_categories, memory_id, content)
    except Exception as e:
        logger.warning(f"Failed to schedule categorization for {memory_id}: {e}")
