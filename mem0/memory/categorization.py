"""
Memory categorization module for self-hosted mem0.

Provides LLM-based memory categorization using user-defined custom categories.
Reference: openmemory/api/app/utils/categorization.py
"""

import json
import logging
from typing import Dict, List, Optional

from mem0.memory.utils import extract_json, remove_code_blocks

logger = logging.getLogger(__name__)

# Prompt template for strict-mode categorization.
# Only categories explicitly listed by the user are allowed.
CUSTOM_CATEGORIZATION_PROMPT_TEMPLATE = """Your task is to assign the given memory to one or more of the following categories.
You MUST only select from the categories listed below. Do NOT create new categories.

Categories:
{formatted_categories}

Guidelines:
- Return only the category names under 'categories' key in JSON format.
- Only use category names exactly as listed above.
- If the memory does not fit any category, return an empty list.
- A memory can belong to multiple categories.
- You should detect the language of the memory and understand it, but always return the category names exactly as listed above (do not translate them).

Example output:
{{"categories": ["category_name_1", "category_name_2"]}}
"""


def _build_categorization_prompt(custom_categories: Dict[str, str]) -> str:
    """Build the system prompt by injecting the user-defined categories.

    Args:
        custom_categories: A dict mapping category name -> description.

    Returns:
        The formatted system prompt string.
    """
    lines = []
    for name, description in custom_categories.items():
        lines.append(f"- {name}: {description}")
    formatted_categories = "\n".join(lines)
    return CUSTOM_CATEGORIZATION_PROMPT_TEMPLATE.format(formatted_categories=formatted_categories)


def categorize_memory(
    llm,
    memory_text: str,
    custom_categories: Dict[str, str],
) -> List[str]:
    """Categorize a single memory using the LLM.

    The function calls the *same* LLM instance that ``Memory`` already uses for
    fact extraction, so no extra client configuration is needed.

    Args:
        llm: The LLM instance (``self.llm`` from ``Memory``).
        memory_text: The text of the memory to categorize.
        custom_categories: A dict mapping category name -> description.
            Only these category names are considered valid.

    Returns:
        A list of matched category names (subset of ``custom_categories.keys()``).
        Returns an empty list on any error so that categorization failures
        never block memory creation.
    """
    if not custom_categories or not memory_text:
        return []

    system_prompt = _build_categorization_prompt(custom_categories)
    valid_names = set(custom_categories.keys())
    # Also build a case-insensitive lookup for robustness
    lower_to_original = {k.lower(): k for k in valid_names}

    try:
        logger.info("[categorize_memory] Starting categorization for memory: %s", memory_text[:100])
        logger.info("[categorize_memory] Custom categories: %s", list(custom_categories.keys()))

        response = llm.generate_response(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": memory_text},
            ],
            response_format={"type": "json_object"},
        )

        logger.info("[categorize_memory] Raw LLM response: %s", response[:500] if response else "<empty>")

        # Parse the JSON response
        if not response or not response.strip():
            logger.warning("[categorize_memory] Empty LLM response during categorization for memory: %s", memory_text[:80])
            return []

        response = remove_code_blocks(response)

        try:
            parsed = json.loads(response)
        except json.JSONDecodeError:
            logger.warning("[categorize_memory] Direct JSON parse failed, trying extract_json. Response: %s", response[:200])
            extracted = extract_json(response)
            parsed = json.loads(extracted)

        logger.info("[categorize_memory] Parsed JSON: %s", parsed)

        raw_categories = parsed.get("categories", [])
        if not isinstance(raw_categories, list):
            logger.warning("[categorize_memory] LLM returned non-list categories: %s", raw_categories)
            return []

        # Strict-mode filtering: only keep categories that exist in custom_categories
        matched = []
        for cat in raw_categories:
            cat_str = str(cat).strip()
            if cat_str in valid_names:
                matched.append(cat_str)
            elif cat_str.lower() in lower_to_original:
                # Accept case-insensitive match but use the original key name
                matched.append(lower_to_original[cat_str.lower()])
            else:
                logger.info("[categorize_memory] Ignoring unknown category from LLM: %s", cat_str)

        logger.info("[categorize_memory] Final matched categories: %s", matched)
        return matched

    except Exception as e:
        logger.warning(
            "[categorize_memory] Failed to categorize memory (will proceed without categories): %s. Memory: %s",
            e,
            memory_text[:80],
        )
        return []
