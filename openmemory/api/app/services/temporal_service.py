"""Temporal and entity extraction service.

This module handles all temporal information extraction from memory facts:
- Building LLM prompts for temporal extraction
- Extracting temporal entities (events, people, places, etc.)
- Enriching metadata with temporal information
- Formatting temporal data for logging
"""

import json
import logging
from datetime import datetime
from typing import Dict, Optional

from app.models.schemas import TemporalEntity

logger = logging.getLogger(__name__)


def build_temporal_extraction_prompt(current_date: datetime) -> str:
    """Build the temporal extraction prompt with the current date context.

    Args:
        current_date: The current date/time for resolving relative time references

    Returns:
        Formatted prompt string with current date context
    """
    return f"""You are an expert at extracting temporal and entity information from memory facts.

Your task is to analyze a memory fact and extract structured information in JSON format:
1. **Entity Types**: Determine if the memory is about events, people, places, promises, or relationships
2. **Temporal Information**: Extract and resolve any time references to actual ISO 8601 timestamps
3. **Named Entities**: List all people, places, and things mentioned
4. **Representation**: Choose a single emoji that captures the essence of the memory

You must return a valid JSON object with the following structure.

**Current Date Context:**
- Today's date: {current_date.strftime("%Y-%m-%d")}
- Current time: {current_date.strftime("%H:%M:%S")}
- Day of week: {current_date.strftime("%A")}

**Time Resolution Guidelines:**

Relative Time References:
- "tomorrow" → Add 1 day to current date
- "next week" → Add 7 days to current date
- "in X days/weeks/months" → Add X time units to current date
- "yesterday" → Subtract 1 day from current date

Time of Day:
- "4pm" or "16:00" → Use current date with that time
- "tomorrow at 4pm" → Use tomorrow's date at 16:00
- "morning" → 09:00, "afternoon" → 14:00, "evening" → 18:00, "night" → 21:00

Duration Estimation (when only start time is mentioned):
- Events like "wedding", "meeting", "party" → Default 2 hours duration
- "lunch", "dinner", "breakfast" → Default 1 hour duration
- "class", "workshop" → Default 1.5 hours duration
- "appointment", "call" → Default 30 minutes duration

**Entity Type Guidelines:**
- **isEvent**: True for scheduled activities, appointments, meetings, parties, ceremonies, classes, etc.
- **isPerson**: True when the primary focus is on a person
- **isPlace**: True when the primary focus is a location
- **isPromise**: True for commitments, promises, or agreements
- **isRelationship**: True for statements about relationships

**Example:**

Input: "I'm taking a glassblowing class today at Wimberly Glassworks with instructor Nick"
Output:
{{
    "isEvent": true,
    "isPerson": true,
    "isPlace": true,
    "isPromise": false,
    "isRelationship": false,
    "entities": ["Wimberly Glassworks", "Nick", "glassblowing"],
    "timeRanges": [
        {{
            "start": "{current_date.replace(hour=10, minute=0, second=0).isoformat()}",
            "end": "{current_date.replace(hour=11, minute=30, second=0).isoformat()}",
            "name": "Glassblowing Class"
        }}
    ],
    "emoji": "🎨"
}}

**Instructions:**
- Return structured data following the TemporalEntity schema
- Convert all temporal references to ISO 8601 format
- Be conservative: if there's no temporal information, leave timeRanges empty
- Multiple tags can be true (e.g., isEvent and isPerson both true for "meeting with John")
- Extract all meaningful entities (people, places, things) mentioned in the fact
- Choose an emoji that best represents the core meaning of the memory
"""


async def extract_temporal_entity(memory_client, fact: str) -> Optional[Dict]:
    """Extract temporal and entity information from a memory fact using LLM.

    Args:
        memory_client: The mem0 memory client (for accessing LLM config)
        fact: The memory fact text to analyze

    Returns:
        Dictionary with temporal/entity information, or None if extraction fails
    """
    try:
        from openai import AsyncOpenAI

        # Get LLM config from memory client
        llm_config = memory_client.config.llm.config

        # Handle different config formats (dict vs object)
        if isinstance(llm_config, dict):
            api_key = llm_config.get('api_key')
            base_url = llm_config.get('openai_base_url')
            model = llm_config.get('model', 'gpt-4o-mini')
        else:
            api_key = llm_config.api_key
            base_url = llm_config.openai_base_url if hasattr(llm_config, 'openai_base_url') else None
            model = llm_config.model if hasattr(llm_config, 'model') else 'gpt-4o-mini'

        # Initialize OpenAI client
        openai_client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url
        )

        # Build the prompt with current date context
        temporal_prompt = build_temporal_extraction_prompt(datetime.now())

        # Call LLM with temporal extraction prompt
        response = await openai_client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": temporal_prompt},
                {"role": "user", "content": f"Extract temporal and entity information from this memory fact:\n\n{fact}"}
            ],
            response_format={"type": "json_object"},
            temperature=0.1
        )

        content = response.choices[0].message.content
        if not content:
            logger.warning("LLM returned empty content for temporal extraction")
            return None

        # Parse and validate with Pydantic
        temporal_data = json.loads(content)

        # Convert timeRanges ISO strings to datetime objects for validation
        if "timeRanges" in temporal_data:
            for time_range in temporal_data["timeRanges"]:
                if isinstance(time_range.get("start"), str):
                    time_range["start"] = datetime.fromisoformat(time_range["start"].replace("Z", "+00:00"))
                if isinstance(time_range.get("end"), str):
                    time_range["end"] = datetime.fromisoformat(time_range["end"].replace("Z", "+00:00"))

        # Validate with Pydantic model
        temporal_entity = TemporalEntity(**temporal_data)

        # Convert back to serializable dict format
        result = {
            "isEvent": temporal_entity.isEvent,
            "isPerson": temporal_entity.isPerson,
            "isPlace": temporal_entity.isPlace,
            "isPromise": temporal_entity.isPromise,
            "isRelationship": temporal_entity.isRelationship,
            "entities": temporal_entity.entities,
            "emoji": temporal_entity.emoji
        }

        # Convert timeRanges to serializable format
        if temporal_entity.timeRanges:
            result["timeRanges"] = []
            for tr in temporal_entity.timeRanges:
                time_range_dict = {
                    "start": tr.start.isoformat() if isinstance(tr.start, datetime) else tr.start,
                    "end": tr.end.isoformat() if isinstance(tr.end, datetime) else tr.end,
                }
                if tr.name:
                    time_range_dict["name"] = tr.name
                result["timeRanges"].append(time_range_dict)
        else:
            result["timeRanges"] = []

        logger.info(f"✅ Temporal extraction: isEvent={result['isEvent']}, entities={len(result['entities'])}, timeRanges={len(result['timeRanges'])}")
        return result

    except Exception as e:
        logger.warning(f"Failed to extract temporal information: {e}")
        return None


async def enrich_metadata_with_temporal_data(
    memory_client,
    fact_content: str,
    base_metadata: dict
) -> tuple[dict, Optional[dict]]:
    """Extract ONLY time-related data (not entity type classifications).

    Adds: timeRanges, entities (useful for search)
    Skips: isEvent, isPerson, emoji (Mycelia-specific)

    Args:
        memory_client: The mem0 memory client
        fact_content: The memory fact content to analyze
        base_metadata: Base metadata dictionary to enrich

    Returns:
        Tuple of (enriched_metadata, temporal_info)
    """
    temporal_info = await extract_temporal_entity(memory_client, fact_content)
    enriched_metadata = base_metadata.copy()

    if temporal_info:
        # Only add time-related data
        if temporal_info.get("timeRanges"):
            enriched_metadata["timeRanges"] = temporal_info["timeRanges"]

        # Entities are useful for search (not Mycelia-specific)
        if temporal_info.get("entities"):
            enriched_metadata["entities"] = temporal_info["entities"]

    return enriched_metadata, temporal_info


async def enrich_metadata_with_mycelia_fields(
    memory_client,
    fact_content: str,
    base_metadata: dict
) -> tuple[dict, Optional[dict]]:
    """Extract FULL temporal/entity info including Mycelia timeline fields.

    Adds: isEvent, isPerson, isPlace, isPromise, isRelationship, emoji, display_name
    Plus: timeRanges, entities

    This requires extra LLM call and is only needed for timeline apps.

    Args:
        memory_client: The mem0 memory client
        fact_content: The memory fact content to analyze
        base_metadata: Base metadata dictionary to enrich

    Returns:
        Tuple of (enriched_metadata, temporal_info)
    """
    temporal_info = await extract_temporal_entity(memory_client, fact_content)
    enriched_metadata = base_metadata.copy()

    if temporal_info:
        enriched_metadata.update({
            "isEvent": temporal_info.get("isEvent", False),
            "isPerson": temporal_info.get("isPerson", False),
            "isPlace": temporal_info.get("isPlace", False),
            "isPromise": temporal_info.get("isPromise", False),
            "isRelationship": temporal_info.get("isRelationship", False),
            "entities": temporal_info.get("entities", []),
            "timeRanges": temporal_info.get("timeRanges", []),
            "emoji": temporal_info.get("emoji")
        })

        # Create display name with emoji if available
        if temporal_info.get("emoji"):
            fact_preview = fact_content[:50] + ("..." if len(fact_content) > 50 else "")
            enriched_metadata["display_name"] = f"{temporal_info['emoji']} {fact_preview}"

    return enriched_metadata, temporal_info


def format_temporal_log_string(temporal_info: Optional[dict]) -> str:
    """Format temporal info for logging.

    Args:
        temporal_info: Dictionary with temporal information or None

    Returns:
        Formatted string for logging, empty if no temporal info
    """
    if not temporal_info:
        return ""
    return f" [emoji={temporal_info.get('emoji')}, isEvent={temporal_info.get('isEvent')}, entities={len(temporal_info.get('entities', []))}]"
