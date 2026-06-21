"""Entity store helpers: upsert, link, remove, and bulk clear."""

import asyncio
import logging
import uuid

from mem0.utils.entity_extraction import extract_entities

logger = logging.getLogger(__name__)


def upsert_entity(memory, entity_text, entity_type, memory_id, filters):
    """Upsert an entity into the entity store, linking it to a memory."""
    try:
        entity_embedding = memory.embedding_model.embed(entity_text, "add")
        search_filters = {k: v for k, v in filters.items() if k in ("user_id", "agent_id", "run_id") and v}

        existing = memory.entity_store.search(
            query=entity_text,
            vectors=entity_embedding,
            top_k=1,
            filters=search_filters,
        )

        if existing and existing[0].score >= 0.95:
            # Update existing entity's linked_memory_ids
            match = existing[0]
            payload = match.payload or {}
            linked_ids = payload.get("linked_memory_ids", [])
            if memory_id not in linked_ids:
                linked_ids.append(memory_id)
                payload["linked_memory_ids"] = linked_ids
                memory.entity_store.update(
                    vector_id=match.id,
                    vector=None,
                    payload=payload,
                )
        else:
            # Create new entity
            entity_id = str(uuid.uuid4())
            entity_payload = {
                "data": entity_text,
                "entity_type": entity_type,
                "linked_memory_ids": [memory_id],
                **{k: v for k, v in search_filters.items()},
            }
            memory.entity_store.insert(
                vectors=[entity_embedding],
                ids=[entity_id],
                payloads=[entity_payload],
            )
    except Exception as e:
        logger.warning(f"Entity upsert failed for '{entity_text}': {e}")


def remove_memory_from_entity_store(memory, memory_id, filters):
    """Strip `memory_id` from every entity record scoped to `filters`.

    For each entity whose `linked_memory_ids` contains `memory_id`:
      - remove the id; if the list becomes empty, delete the entity record.
      - otherwise re-embed the entity text and update the payload
        (the vector store's update() requires a vector).

    No-op if the entity store has never been initialized in this process.
    Errors on individual entities are swallowed at debug level; outer
    failures are swallowed at warning level so the primary delete/update
    path is never broken by entity cleanup.
    """
    if memory._entity_store is None:
        return
    search_filters = {k: v for k, v in filters.items() if k in ("user_id", "agent_id", "run_id") and v}
    try:
        listed = memory.entity_store.list(filters=search_filters, top_k=10000)
        rows = listed[0] if isinstance(listed, (list, tuple)) and listed and isinstance(listed[0], list) else listed
        for row in rows or []:
            try:
                payload = getattr(row, "payload", None) or {}
                linked = payload.get("linked_memory_ids", [])
                if not isinstance(linked, list) or memory_id not in linked:
                    continue
                remaining = [mid for mid in linked if mid != memory_id]
                if not remaining:
                    try:
                        memory.entity_store.delete(vector_id=row.id)
                    except Exception as e:
                        logger.debug(f"Entity delete failed for id={row.id}: {e}")
                else:
                    entity_text = payload.get("data")
                    if not isinstance(entity_text, str) or not entity_text:
                        logger.debug(f"Entity id={row.id} missing 'data'; skipping update during cleanup")
                        continue
                    try:
                        vec = memory.embedding_model.embed(entity_text, "update")
                    except Exception as e:
                        logger.debug(f"Entity re-embed failed for '{entity_text}': {e}")
                        continue
                    new_payload = {**payload, "linked_memory_ids": remaining}
                    try:
                        memory.entity_store.update(
                            vector_id=row.id,
                            vector=vec,
                            payload=new_payload,
                        )
                    except Exception as e:
                        logger.debug(f"Entity update failed for id={row.id}: {e}")
            except Exception as e:
                logger.debug(f"Entity cleanup error: {e}")
    except Exception as e:
        logger.warning(f"Entity store cleanup failed for memory_id={memory_id}: {e}")


def link_entities_for_memory(memory, memory_id, text, filters):
    """Extract entities from `text` and link them to `memory_id` in the
    entity store, scoped to `filters`. Simpler single-memory variant of
    Phase 7 in add(): per-entity search-then-update-or-insert via the
    existing `_upsert_entity` helper. Non-fatal on any failure.
    """
    try:
        entities = extract_entities(text)
        if not entities:
            return
        seen = set()
        for entity_type, entity_text in entities:
            key = entity_text.strip().lower()
            if not key or key in seen:
                continue
            seen.add(key)
            try:
                upsert_entity(memory, entity_text, entity_type, memory_id, filters)
            except Exception as e:
                logger.debug(f"Entity link failed for '{entity_text}': {e}")
    except Exception as e:
        logger.warning(f"Entity linking failed for memory_id={memory_id}: {e}")


async def upsert_entity_async(memory, entity_text, entity_type, memory_id, filters):
    """Async variant of `_upsert_entity` — per-entity search-then-update-or-insert."""
    try:
        entity_embedding = await asyncio.to_thread(memory.embedding_model.embed, entity_text, "add")
        search_filters = {k: v for k, v in filters.items() if k in ("user_id", "agent_id", "run_id") and v}

        existing = await asyncio.to_thread(
            memory.entity_store.search,
            query=entity_text,
            vectors=entity_embedding,
            top_k=1,
            filters=search_filters,
        )

        if existing and existing[0].score >= 0.95:
            match = existing[0]
            payload = match.payload or {}
            linked_ids = payload.get("linked_memory_ids", [])
            if memory_id not in linked_ids:
                linked_ids.append(memory_id)
                payload["linked_memory_ids"] = linked_ids
                await asyncio.to_thread(
                    memory.entity_store.update,
                    vector_id=match.id,
                    vector=None,
                    payload=payload,
                )
        else:
            entity_id = str(uuid.uuid4())
            entity_payload = {
                "data": entity_text,
                "entity_type": entity_type,
                "linked_memory_ids": [memory_id],
                **{k: v for k, v in search_filters.items()},
            }
            await asyncio.to_thread(
                memory.entity_store.insert,
                vectors=[entity_embedding],
                ids=[entity_id],
                payloads=[entity_payload],
            )
    except Exception as e:
        logger.warning(f"Entity upsert failed for '{entity_text}' (async): {e}")


async def bulk_clear_entity_store(memory, filters):
    """Delete all entity records matching the given scope filters.

    Used by delete_all to avoid the race condition that occurs when
    concurrent _delete_memory coroutines each try to read-modify-write
    the same entity rows' linked_memory_ids lists.
    """
    if memory._entity_store is None:
        return
    search_filters = {k: v for k, v in filters.items() if k in ("user_id", "agent_id", "run_id") and v}
    try:
        listed = await asyncio.to_thread(memory.entity_store.list, filters=search_filters, top_k=10000)
        rows = listed[0] if isinstance(listed, (list, tuple)) and listed and isinstance(listed[0], list) else listed
        for row in rows or []:
            try:
                await asyncio.to_thread(memory.entity_store.delete, vector_id=row.id)
            except Exception as e:
                logger.debug(f"Bulk entity delete failed for id={row.id}: {e}")
    except Exception as e:
        logger.warning(f"Bulk entity store cleanup failed: {e}")


async def remove_memory_from_entity_store_async(memory, memory_id, filters):
    """Async variant of `Memory._remove_memory_from_entity_store`."""
    if memory._entity_store is None:
        return
    search_filters = {k: v for k, v in filters.items() if k in ("user_id", "agent_id", "run_id") and v}
    try:
        listed = await asyncio.to_thread(memory.entity_store.list, filters=search_filters, top_k=10000)
        rows = listed[0] if isinstance(listed, (list, tuple)) and listed and isinstance(listed[0], list) else listed
        for row in rows or []:
            try:
                payload = getattr(row, "payload", None) or {}
                linked = payload.get("linked_memory_ids", [])
                if not isinstance(linked, list) or memory_id not in linked:
                    continue
                remaining = [mid for mid in linked if mid != memory_id]
                if not remaining:
                    try:
                        await asyncio.to_thread(memory.entity_store.delete, vector_id=row.id)
                    except Exception as e:
                        logger.debug(f"Entity delete failed for id={row.id} (async): {e}")
                else:
                    entity_text = payload.get("data")
                    if not isinstance(entity_text, str) or not entity_text:
                        logger.debug(f"Entity id={row.id} missing 'data'; skipping update during cleanup (async)")
                        continue
                    try:
                        vec = await asyncio.to_thread(memory.embedding_model.embed, entity_text, "update")
                    except Exception as e:
                        logger.debug(f"Entity re-embed failed for '{entity_text}' (async): {e}")
                        continue
                    new_payload = {**payload, "linked_memory_ids": remaining}
                    try:
                        await asyncio.to_thread(
                            memory.entity_store.update,
                            vector_id=row.id,
                            vector=vec,
                            payload=new_payload,
                        )
                    except Exception as e:
                        logger.debug(f"Entity update failed for id={row.id} (async): {e}")
            except Exception as e:
                logger.debug(f"Entity cleanup error (async): {e}")
    except Exception as e:
        logger.warning(f"Entity store cleanup failed for memory_id={memory_id} (async): {e}")


async def link_entities_for_memory_async(memory, memory_id, text, filters):
    """Async variant of `Memory._link_entities_for_memory`."""
    try:
        entities = await asyncio.to_thread(extract_entities, text)
        if not entities:
            return
        seen = set()
        for entity_type, entity_text in entities:
            key = entity_text.strip().lower()
            if not key or key in seen:
                continue
            seen.add(key)
            try:
                await upsert_entity_async(memory, entity_text, entity_type, memory_id, filters)
            except Exception as e:
                logger.debug(f"Entity link failed for '{entity_text}' (async): {e}")
    except Exception as e:
        logger.warning(f"Entity linking failed for memory_id={memory_id} (async): {e}")

