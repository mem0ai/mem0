"""Search and retrieval internals: vector search, metadata filters, entity boosts."""

import asyncio
import concurrent.futures
import logging
from typing import Any, Dict

from mem0.configs.base import MemoryItem
from mem0.utils.entity_extraction import extract_entities
from mem0.utils.lemmatization import lemmatize_for_bm25
from mem0.utils.scoring import (
    ENTITY_BOOST_WEIGHT,
    get_bm25_params,
    normalize_bm25,
    score_and_rank,
)

logger = logging.getLogger(__name__)

PROMOTED_PAYLOAD_KEYS = [
    "user_id",
    "agent_id",
    "run_id",
    "actor_id",
    "role",
]
CORE_AND_PROMOTED_KEYS = {
    "data",
    "hash",
    "created_at",
    "updated_at",
    "id",
    "text_lemmatized",
    "attributed_to",
    *PROMOTED_PAYLOAD_KEYS,
}


def _format_list_results(actual_memories):
    formatted_memories = []
    for mem in actual_memories:
        memory_item_dict = MemoryItem(
            id=mem.id,
            memory=mem.payload.get("data", ""),
            hash=mem.payload.get("hash"),
            created_at=mem.payload.get("created_at"),
            updated_at=mem.payload.get("updated_at"),
        ).model_dump(exclude={"score"})

        for key in PROMOTED_PAYLOAD_KEYS:
            if key in mem.payload:
                memory_item_dict[key] = mem.payload[key]

        additional_metadata = {k: v for k, v in mem.payload.items() if k not in CORE_AND_PROMOTED_KEYS}
        if additional_metadata:
            memory_item_dict["metadata"] = additional_metadata

        formatted_memories.append(memory_item_dict)
    return formatted_memories


def _unwrap_list_results(memories_result):
    if isinstance(memories_result, (tuple, list)) and len(memories_result) > 0:
        first_element = memories_result[0]
        if isinstance(first_element, (list, tuple)):
            return first_element
        return memories_result
    return memories_result


def get_all_from_vector_store(memory, filters, limit):
    memories_result = memory.vector_store.list(filters=filters, top_k=limit)
    actual_memories = _unwrap_list_results(memories_result)
    return _format_list_results(actual_memories)


async def get_all_from_vector_store_async(memory, filters, limit):
    memories_result = await asyncio.to_thread(memory.vector_store.list, filters=filters, top_k=limit)
    actual_memories = _unwrap_list_results(memories_result)
    return _format_list_results(actual_memories)


def process_metadata_filters(metadata_filters: Dict[str, Any]) -> Dict[str, Any]:
    """
    Process enhanced metadata filters and convert them to vector store compatible format.

    Args:
        metadata_filters: Enhanced metadata filters with operators

    Returns:
        Dict of processed filters compatible with vector store
    """
    processed_filters = {}

    def process_condition(key: str, condition: Any) -> Dict[str, Any]:
        if not isinstance(condition, dict):
            # Simple equality: {"key": "value"}
            if condition == "*":
                # Wildcard: match everything for this field (implementation depends on vector store)
                return {key: "*"}
            return {key: condition}

        result = {}
        for operator, value in condition.items():
            # Map platform operators to universal format that can be translated by each vector store
            operator_map = {
                "eq": "eq", "ne": "ne", "gt": "gt", "gte": "gte",
                "lt": "lt", "lte": "lte", "in": "in", "nin": "nin",
                "contains": "contains", "icontains": "icontains"
            }

            if operator in operator_map:
                result.setdefault(key, {})[operator_map[operator]] = value
            else:
                raise ValueError(f"Unsupported metadata filter operator: {operator}")
        return result

    def merge_filters(target: Dict[str, Any], source: Dict[str, Any]) -> None:
        """Merge source into target, deep-merging nested operator dicts for the same key."""
        for key, value in source.items():
            if key in target and isinstance(target[key], dict) and isinstance(value, dict):
                target[key].update(value)
            else:
                target[key] = value

    for key, value in metadata_filters.items():
        if key == "AND":
            # Logical AND: combine multiple conditions
            if not isinstance(value, list):
                raise ValueError("AND operator requires a list of conditions")
            for condition in value:
                for sub_key, sub_value in condition.items():
                    merge_filters(processed_filters, process_condition(sub_key, sub_value))
        elif key == "OR":
            # Logical OR: Pass through to vector store for implementation-specific handling
            if not isinstance(value, list) or not value:
                raise ValueError("OR operator requires a non-empty list of conditions")
            # Store OR conditions in a way that vector stores can interpret
            processed_filters["$or"] = []
            for condition in value:
                or_condition = {}
                for sub_key, sub_value in condition.items():
                    merge_filters(or_condition, process_condition(sub_key, sub_value))
                processed_filters["$or"].append(or_condition)
        elif key == "NOT":
            # Logical NOT: Pass through to vector store for implementation-specific handling
            if not isinstance(value, list) or not value:
                raise ValueError("NOT operator requires a non-empty list of conditions")
            processed_filters["$not"] = []
            for condition in value:
                not_condition = {}
                for sub_key, sub_value in condition.items():
                    merge_filters(not_condition, process_condition(sub_key, sub_value))
                processed_filters["$not"].append(not_condition)
        else:
            merge_filters(processed_filters, process_condition(key, value))

    return processed_filters


def has_advanced_operators(filters: Dict[str, Any]) -> bool:
    """
    Check if filters contain advanced operators that need special processing.
    
    Args:
        filters: Dictionary of filters to check
        
    Returns:
        bool: True if advanced operators are detected
    """
    if not isinstance(filters, dict):
        return False
        
    for key, value in filters.items():
        # Check for platform-style logical operators
        if key in ["AND", "OR", "NOT"]:
            return True
        # Check for comparison operators (without $ prefix for universal compatibility)
        if isinstance(value, dict):
            for op in value.keys():
                if op in ["eq", "ne", "gt", "gte", "lt", "lte", "in", "nin", "contains", "icontains"]:
                    return True
        # Check for wildcard values
        if value == "*":
            return True
    return False


def search_vector_store(memory, query, filters, limit, threshold=0.1, explain=False):
    # Guard against None threshold (backward compat)
    if threshold is None:
        threshold = 0.1

    # Step 1: Preprocess query
    query_lemmatized = lemmatize_for_bm25(query)
    query_entities = extract_entities(query)

    # Step 2: Embed query
    embeddings = memory.embedding_model.embed(query, "search")

    # Step 3: Semantic search (over-fetch for scoring pool)
    internal_limit = max(limit * 4, 60)
    semantic_results = memory.vector_store.search(
        query=query, vectors=embeddings, top_k=internal_limit, filters=filters
    )

    # Step 4: Keyword search (if store supports it)
    keyword_results = memory.vector_store.keyword_search(
        query=query_lemmatized, top_k=internal_limit, filters=filters
    )

    # Step 5: Compute BM25 scores from keyword results
    bm25_scores = {}
    if keyword_results is not None:
        midpoint, steepness = get_bm25_params(query, lemmatized=query_lemmatized)
        for mem in keyword_results:
            mem_id = str(mem.id) if hasattr(mem, 'id') else str(mem.get('id', ''))
            raw_score = mem.score if hasattr(mem, 'score') else mem.get('score', 0)
            if raw_score and raw_score > 0:
                bm25_scores[mem_id] = normalize_bm25(raw_score, midpoint, steepness)

    # Step 6: Compute entity boosts
    entity_boosts = {}
    if query_entities:
        entity_boosts = compute_entity_boosts(memory, query_entities, filters)

    # Step 7: Build candidate set from semantic results
    candidates = []
    for mem in semantic_results:
        mem_id = str(mem.id)
        candidates.append({
            "id": mem_id,
            "score": mem.score,
            "payload": mem.payload if hasattr(mem, 'payload') else {},
        })

    # Step 8: Score and rank
    scored_results = score_and_rank(
        semantic_results=candidates,
        bm25_scores=bm25_scores,
        entity_boosts=entity_boosts,
        threshold=threshold,
        top_k=limit,
        explain=explain,
    )

    # Step 9: Format results
    promoted_payload_keys = [
        "user_id",
        "agent_id",
        "run_id",
        "actor_id",
        "role",
    ]
    core_and_promoted_keys = {"data", "hash", "created_at", "updated_at", "id", "text_lemmatized", "attributed_to", *promoted_payload_keys}

    original_memories = []
    for scored in scored_results:
        payload = scored.get("payload") or {}

        if not payload.get("data"):
            continue  # Skip candidates with no payload data

        memory_item_dict = MemoryItem(
            id=scored["id"],
            memory=payload.get("data", ""),
            hash=payload.get("hash"),
            created_at=payload.get("created_at"),
            updated_at=payload.get("updated_at"),
            score=scored["score"],
        ).model_dump()

        for key in promoted_payload_keys:
            if key in payload:
                memory_item_dict[key] = payload[key]

        additional_metadata = {k: v for k, v in payload.items() if k not in core_and_promoted_keys}
        if additional_metadata:
            if not memory_item_dict.get("metadata"):
                memory_item_dict["metadata"] = {}
            memory_item_dict["metadata"].update(additional_metadata)
        if explain and "score_details" in scored:
            memory_item_dict["score_details"] = scored["score_details"]

        original_memories.append(memory_item_dict)

    return original_memories


async def search_vector_store_async(memory, query, filters, limit, threshold=0.1, explain=False):
    if threshold is None:
        threshold = 0.1

    # Step 1: Preprocess query (CPU-bound)
    query_lemmatized = await asyncio.to_thread(lemmatize_for_bm25, query)
    query_entities = await asyncio.to_thread(extract_entities, query)

    # Step 2: Embed query
    embeddings = await asyncio.to_thread(memory.embedding_model.embed, query, "search")

    # Step 3: Semantic search (over-fetch)
    internal_limit = max(limit * 4, 60)
    semantic_results = await asyncio.to_thread(
        memory.vector_store.search, query=query, vectors=embeddings, top_k=internal_limit, filters=filters
    )

    # Step 4: Keyword search (if store supports it)
    keyword_results = await asyncio.to_thread(
        memory.vector_store.keyword_search, query=query_lemmatized, top_k=internal_limit, filters=filters
    )

    # Step 5: Compute BM25 scores
    bm25_scores = {}
    if keyword_results is not None:
        midpoint, steepness = get_bm25_params(query, lemmatized=query_lemmatized)
        for mem in keyword_results:
            mem_id = str(mem.id) if hasattr(mem, 'id') else str(mem.get('id', ''))
            raw_score = mem.score if hasattr(mem, 'score') else mem.get('score', 0)
            if raw_score and raw_score > 0:
                bm25_scores[mem_id] = normalize_bm25(raw_score, midpoint, steepness)

    # Step 6: Compute entity boosts
    entity_boosts = {}
    if query_entities:
        entity_boosts = await compute_entity_boosts_async(memory, query_entities, filters)

    # Step 7: Build candidate set from semantic results
    candidates = []
    for mem in semantic_results:
        mem_id = str(mem.id)
        candidates.append({
            "id": mem_id,
            "score": mem.score,
            "payload": mem.payload if hasattr(mem, 'payload') else {},
        })

    # Step 8: Score and rank
    scored_results = score_and_rank(
        semantic_results=candidates,
        bm25_scores=bm25_scores,
        entity_boosts=entity_boosts,
        threshold=threshold,
        top_k=limit,
        explain=explain,
    )

    # Step 9: Format results
    promoted_payload_keys = [
        "user_id",
        "agent_id",
        "run_id",
        "actor_id",
        "role",
    ]
    core_and_promoted_keys = {"data", "hash", "created_at", "updated_at", "id", "text_lemmatized", "attributed_to", *promoted_payload_keys}

    original_memories = []
    for scored in scored_results:
        payload = scored.get("payload") or {}
        if not payload.get("data"):
            continue

        memory_item_dict = MemoryItem(
            id=scored["id"],
            memory=payload.get("data", ""),
            hash=payload.get("hash"),
            created_at=payload.get("created_at"),
            updated_at=payload.get("updated_at"),
            score=scored["score"],
        ).model_dump()

        for key in promoted_payload_keys:
            if key in payload:
                memory_item_dict[key] = payload[key]

        additional_metadata = {k: v for k, v in payload.items() if k not in core_and_promoted_keys}
        if additional_metadata:
            if not memory_item_dict.get("metadata"):
                memory_item_dict["metadata"] = {}
            memory_item_dict["metadata"].update(additional_metadata)
        if explain and "score_details" in scored:
            memory_item_dict["score_details"] = scored["score_details"]

        original_memories.append(memory_item_dict)

    return original_memories


def compute_entity_boosts(memory, query_entities, filters):
    """Compute per-memory entity boosts from entity store search.

    For each extracted entity from the query:
    1. Embed the entity text
    2. Search the entity store (threshold >= 0.5)
    3. For each matched entity, boost its linked memories

    Returns:
        Dict mapping memory_id (str) -> max entity boost [0, 0.5].
    """
    # Deduplicate entities (max 8)
    seen = set()
    deduped = []
    for entity_type, entity_text in query_entities[:8]:
        key = entity_text.strip().lower()
        if key and key not in seen:
            seen.add(key)
            deduped.append((entity_type, entity_text))

    if not deduped:
        return {}

    search_filters = {k: v for k, v in filters.items() if k in ("user_id", "agent_id", "run_id") and v}
    memory_boosts = {}

    try:
        entity_texts = [text for _, text in deduped]
        embeddings = memory.embedding_model.embed_batch(entity_texts, "search")

        if len(embeddings) != len(entity_texts):
            logger.warning(
                "embed_batch returned %d vectors for %d texts — skipping entity boost",
                len(embeddings),
                len(entity_texts),
            )
            return memory_boosts

        entity_store = memory.entity_store

        def _search_entity(entity_text, embedding):
            return entity_store.search(
                query=entity_text, vectors=embedding, top_k=500, filters=search_filters
            )

        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            futures = {
                pool.submit(_search_entity, text, emb): text
                for text, emb in zip(entity_texts, embeddings)
            }

            for future in concurrent.futures.as_completed(futures):
                try:
                    matches = future.result()
                except Exception as e:
                    logger.warning("Entity boost search failed for one entity: %s", e)
                    continue

                for match in matches:
                    similarity = match.score if hasattr(match, 'score') else 0.0
                    if similarity < 0.5:
                        continue

                    payload = match.payload if hasattr(match, 'payload') else {}
                    linked_memory_ids = payload.get("linked_memory_ids", [])
                    if not isinstance(linked_memory_ids, list):
                        continue

                    num_linked = max(len(linked_memory_ids), 1)
                    memory_count_weight = 1.0 / (1.0 + 0.001 * ((num_linked - 1) ** 2))
                    boost = similarity * ENTITY_BOOST_WEIGHT * memory_count_weight

                    for memory_id in linked_memory_ids:
                        if memory_id:
                            memory_key = str(memory_id)
                            memory_boosts[memory_key] = max(memory_boosts.get(memory_key, 0.0), boost)

    except Exception as e:
        logger.warning(f"Entity boost computation failed: {e}")

    return memory_boosts


async def compute_entity_boosts_async(memory, query_entities, filters):
    """Async version of entity boost computation."""
    seen = set()
    deduped = []
    for entity_type, entity_text in query_entities[:8]:
        key = entity_text.strip().lower()
        if key and key not in seen:
            seen.add(key)
            deduped.append((entity_type, entity_text))

    if not deduped:
        return {}

    search_filters = {k: v for k, v in filters.items() if k in ("user_id", "agent_id", "run_id") and v}
    memory_boosts = {}

    try:
        entity_texts = [text for _, text in deduped]
        embeddings = await asyncio.to_thread(memory.embedding_model.embed_batch, entity_texts, "search")

        if len(embeddings) != len(entity_texts):
            logger.warning(
                "embed_batch returned %d vectors for %d texts — skipping entity boost",
                len(embeddings),
                len(entity_texts),
            )
            return memory_boosts

        sem = asyncio.Semaphore(4)

        async def _search_entity(entity_text, embedding):
            async with sem:
                return await asyncio.to_thread(
                    memory.entity_store.search,
                    query=entity_text,
                    vectors=embedding,
                    top_k=500,
                    filters=search_filters,
                )

        results = await asyncio.gather(
            *(_search_entity(text, emb) for text, emb in zip(entity_texts, embeddings)),
            return_exceptions=True,
        )

        for matches in results:
            if isinstance(matches, BaseException):
                logger.warning("Entity boost search failed for one entity: %s", matches)
                continue

            for match in matches:
                similarity = match.score if hasattr(match, 'score') else 0.0
                if similarity < 0.5:
                    continue

                payload = match.payload if hasattr(match, 'payload') else {}
                linked_memory_ids = payload.get("linked_memory_ids", [])
                if not isinstance(linked_memory_ids, list):
                    continue

                num_linked = max(len(linked_memory_ids), 1)
                memory_count_weight = 1.0 / (1.0 + 0.001 * ((num_linked - 1) ** 2))
                boost = similarity * ENTITY_BOOST_WEIGHT * memory_count_weight

                for memory_id in linked_memory_ids:
                    if memory_id:
                        memory_key = str(memory_id)
                        memory_boosts[memory_key] = max(memory_boosts.get(memory_key, 0.0), boost)

    except Exception as e:
        logger.warning(f"Entity boost computation failed: {e}")

    return memory_boosts

