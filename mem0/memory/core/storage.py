"""Vector-store CRUD helpers: create, update, and delete memories."""

import asyncio
import hashlib
import logging
import uuid
from copy import deepcopy
from datetime import datetime, timezone

from mem0.memory.core.config import _normalize_iso_timestamp_to_utc
from mem0.memory.core.entities import (
    link_entities_for_memory,
    link_entities_for_memory_async,
    remove_memory_from_entity_store,
    remove_memory_from_entity_store_async,
)
from mem0.utils.lemmatization import lemmatize_for_bm25

logger = logging.getLogger(__name__)


def create_memory(memory, data, existing_embeddings, metadata=None):
    logger.debug(f"Creating memory with {data=}")
    if data in existing_embeddings:
        embeddings = existing_embeddings[data]
    else:
        embeddings = memory.embedding_model.embed(data, memory_action="add")
    memory_id = str(uuid.uuid4())
    new_metadata = deepcopy(metadata) if metadata is not None else {}
    new_metadata["data"] = data
    new_metadata["hash"] = hashlib.md5(data.encode()).hexdigest()
    if "created_at" not in new_metadata:
        new_metadata["created_at"] = datetime.now(timezone.utc).isoformat()
    new_metadata["updated_at"] = new_metadata["created_at"]
    new_metadata["text_lemmatized"] = lemmatize_for_bm25(data)

    memory.vector_store.insert(
        vectors=[embeddings],
        ids=[memory_id],
        payloads=[new_metadata],
    )
    memory.db.add_history(
        memory_id,
        None,
        data,
        "ADD",
        created_at=new_metadata.get("created_at"),
        updated_at=new_metadata.get("updated_at"),
        actor_id=new_metadata.get("actor_id"),
        role=new_metadata.get("role"),
    )
    return memory_id


def update_memory(memory, memory_id, data, existing_embeddings, metadata=None):
    logger.info(f"Updating memory with {data=}")

    try:
        existing_memory = memory.vector_store.get(vector_id=memory_id)
    except Exception:
        logger.error(f"Error getting memory with ID {memory_id} during update.")
        raise ValueError(f"Error getting memory with ID {memory_id}. Please provide a valid 'memory_id'")

    if existing_memory is None:
        raise ValueError(f"Memory with id {memory_id} not found. Please provide a valid 'memory_id'")

    prev_value = existing_memory.payload.get("data")

    new_metadata = deepcopy(existing_memory.payload)
    if metadata is not None:
        new_metadata.update(metadata)

    new_metadata["data"] = data
    new_metadata["hash"] = hashlib.md5(data.encode()).hexdigest()
    new_metadata["text_lemmatized"] = lemmatize_for_bm25(data)
    new_metadata["created_at"] = existing_memory.payload.get("created_at")
    new_metadata["updated_at"] = datetime.now(timezone.utc).isoformat()

    # actor_id is immutable after creation (issue #4490)
    if "actor_id" in existing_memory.payload:
        new_metadata["actor_id"] = existing_memory.payload["actor_id"]

    if data in existing_embeddings:
        embeddings = existing_embeddings[data]
    else:
        embeddings = memory.embedding_model.embed(data, "update")

    memory.vector_store.update(
        vector_id=memory_id,
        vector=embeddings,
        payload=new_metadata,
    )
    logger.info(f"Updating memory with ID {memory_id=} with {data=}")

    memory.db.add_history(
        memory_id,
        prev_value,
        data,
        "UPDATE",
        created_at=new_metadata["created_at"],
        updated_at=new_metadata["updated_at"],
        actor_id=new_metadata.get("actor_id"),
        role=new_metadata.get("role"),
    )

    # Entity-store cleanup: strip this memory's id from old-text entities,
    # then re-extract entities from the new text and link them back.
    session_filters = {k: new_metadata[k] for k in ("user_id", "agent_id", "run_id") if new_metadata.get(k)}
    remove_memory_from_entity_store(memory, memory_id, session_filters)
    link_entities_for_memory(memory, memory_id, data, session_filters)

    return memory_id


def delete_memory(memory, memory_id, existing_memory=None):
    logger.info(f"Deleting memory with {memory_id=}")
    if existing_memory is None:
        existing_memory = memory.vector_store.get(vector_id=memory_id)
        if existing_memory is None:
            raise ValueError(f"Memory with id {memory_id} not found. Please provide a valid 'memory_id'")
    prev_value = existing_memory.payload.get("data", "")
    created_at = _normalize_iso_timestamp_to_utc(existing_memory.payload.get("created_at"))
    updated_at = datetime.now(timezone.utc).isoformat()
    payload = existing_memory.payload or {}
    session_filters = {k: payload[k] for k in ("user_id", "agent_id", "run_id") if payload.get(k)}
    memory.vector_store.delete(vector_id=memory_id)
    memory.db.add_history(
        memory_id,
        prev_value,
        None,
        "DELETE",
        created_at=created_at,
        updated_at=updated_at,
        actor_id=existing_memory.payload.get("actor_id"),
        role=existing_memory.payload.get("role"),
        is_deleted=1,
    )

    # Entity-store cleanup: strip this memory's id from any entity records
    # that linked to it. Non-fatal — the helper swallows errors.
    remove_memory_from_entity_store(memory, memory_id, session_filters)

    return memory_id


async def create_memory_async(memory, data, existing_embeddings, metadata=None):
    logger.debug(f"Creating memory with {data=}")
    if data in existing_embeddings:
        embeddings = existing_embeddings[data]
    else:
        embeddings = await asyncio.to_thread(memory.embedding_model.embed, data, memory_action="add")

    memory_id = str(uuid.uuid4())
    new_metadata = deepcopy(metadata) if metadata is not None else {}
    new_metadata["data"] = data
    new_metadata["hash"] = hashlib.md5(data.encode()).hexdigest()
    if "created_at" not in new_metadata:
        new_metadata["created_at"] = datetime.now(timezone.utc).isoformat()
    new_metadata["updated_at"] = new_metadata["created_at"]
    new_metadata["text_lemmatized"] = lemmatize_for_bm25(data)

    await asyncio.to_thread(
        memory.vector_store.insert,
        vectors=[embeddings],
        ids=[memory_id],
        payloads=[new_metadata],
    )

    await asyncio.to_thread(
        memory.db.add_history,
        memory_id,
        None,
        data,
        "ADD",
        created_at=new_metadata.get("created_at"),
        updated_at=new_metadata.get("updated_at"),
        actor_id=new_metadata.get("actor_id"),
        role=new_metadata.get("role"),
    )

    return memory_id


async def update_memory_async(memory, memory_id, data, existing_embeddings, metadata=None):
    logger.info(f"Updating memory with {data=}")

    try:
        existing_memory = await asyncio.to_thread(memory.vector_store.get, vector_id=memory_id)
    except Exception:
        logger.error(f"Error getting memory with ID {memory_id} during update.")
        raise ValueError(f"Error getting memory with ID {memory_id}. Please provide a valid 'memory_id'")

    if existing_memory is None:
        raise ValueError(f"Memory with id {memory_id} not found. Please provide a valid 'memory_id'")

    prev_value = existing_memory.payload.get("data")

    new_metadata = deepcopy(existing_memory.payload)
    if metadata is not None:
        new_metadata.update(metadata)

    new_metadata["data"] = data
    new_metadata["hash"] = hashlib.md5(data.encode()).hexdigest()
    new_metadata["text_lemmatized"] = lemmatize_for_bm25(data)
    new_metadata["created_at"] = existing_memory.payload.get("created_at")
    new_metadata["updated_at"] = datetime.now(timezone.utc).isoformat()

    # actor_id is immutable after creation (issue #4490)
    if "actor_id" in existing_memory.payload:
        new_metadata["actor_id"] = existing_memory.payload["actor_id"]

    if data in existing_embeddings:
        embeddings = existing_embeddings[data]
    else:
        embeddings = await asyncio.to_thread(memory.embedding_model.embed, data, "update")

    await asyncio.to_thread(
        memory.vector_store.update,
        vector_id=memory_id,
        vector=embeddings,
        payload=new_metadata,
    )
    logger.info(f"Updating memory with ID {memory_id=} with {data=}")

    await asyncio.to_thread(
        memory.db.add_history,
        memory_id,
        prev_value,
        data,
        "UPDATE",
        created_at=new_metadata["created_at"],
        updated_at=new_metadata["updated_at"],
        actor_id=new_metadata.get("actor_id"),
        role=new_metadata.get("role"),
    )

    # Entity-store cleanup: strip this memory's id from old-text entities,
    # then re-extract entities from the new text and link them back.
    session_filters = {k: new_metadata[k] for k in ("user_id", "agent_id", "run_id") if new_metadata.get(k)}
    await remove_memory_from_entity_store_async(memory, memory_id, session_filters)
    await link_entities_for_memory_async(memory, memory_id, data, session_filters)

    return memory_id


async def delete_memory_async(memory, memory_id, existing_memory=None, skip_entity_cleanup=False):
    logger.info(f"Deleting memory with {memory_id=}")
    if existing_memory is None:
        existing_memory = await asyncio.to_thread(memory.vector_store.get, vector_id=memory_id)
        if existing_memory is None:
            raise ValueError(f"Memory with id {memory_id} not found. Please provide a valid 'memory_id'")
    prev_value = existing_memory.payload.get("data", "")
    created_at = _normalize_iso_timestamp_to_utc(existing_memory.payload.get("created_at"))
    updated_at = datetime.now(timezone.utc).isoformat()
    payload = existing_memory.payload or {}
    session_filters = {k: payload[k] for k in ("user_id", "agent_id", "run_id") if payload.get(k)}

    await asyncio.to_thread(memory.vector_store.delete, vector_id=memory_id)
    await asyncio.to_thread(
        memory.db.add_history,
        memory_id,
        prev_value,
        None,
        "DELETE",
        created_at=created_at,
        updated_at=updated_at,
        actor_id=existing_memory.payload.get("actor_id"),
        role=existing_memory.payload.get("role"),
        is_deleted=1,
    )

    if not skip_entity_cleanup:
        await remove_memory_from_entity_store_async(memory, memory_id, session_filters)

    return memory_id

