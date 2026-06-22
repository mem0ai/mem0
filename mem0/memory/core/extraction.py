"""Memory extraction pipeline: infer/add path and procedural memory creation."""

import asyncio
import hashlib
import json
import logging
import uuid
from copy import deepcopy
from datetime import datetime, timezone

from mem0.configs.enums import MemoryType
from mem0.configs.prompts import (
    ADDITIVE_EXTRACTION_PROMPT,
    AGENT_CONTEXT_SUFFIX,
    PROCEDURAL_MEMORY_SYSTEM_PROMPT,
    generate_additive_extraction_prompt,
)
from mem0.memory.core.filters import _build_session_scope
from mem0.memory.telemetry import capture_event
from mem0.memory.utils import extract_json, parse_messages, process_telemetry_filters, remove_code_blocks
from mem0.utils.entity_extraction import extract_entities_batch
from mem0.utils.lemmatization import lemmatize_for_bm25

logger = logging.getLogger(__name__)


def should_use_agent_memory_extraction(messages, metadata) -> bool:
    """Determine whether to use agent memory extraction."""
    has_agent_id = metadata.get("agent_id") is not None
    has_assistant_messages = any(msg.get("role") == "assistant" for msg in messages)
    return has_agent_id and has_assistant_messages


def add_to_vector_store(memory, messages, metadata, filters, infer, prompt=None):
    if not infer:
        returned_memories = []
        for message_dict in messages:
            if (
                not isinstance(message_dict, dict)
                or message_dict.get("role") is None
                or message_dict.get("content") is None
            ):
                logger.warning(f"Skipping invalid message format: {message_dict}")
                continue

            if message_dict["role"] == "system":
                continue

            per_msg_meta = deepcopy(metadata)
            per_msg_meta["role"] = message_dict["role"]

            actor_name = message_dict.get("name")
            if actor_name:
                per_msg_meta["actor_id"] = actor_name

            msg_content = message_dict["content"]
            msg_embeddings = memory.embedding_model.embed(msg_content, "add")
            mem_id = memory._create_memory(msg_content, {msg_content: msg_embeddings}, per_msg_meta)

            returned_memories.append(
                {
                    "id": mem_id,
                    "memory": msg_content,
                    "event": "ADD",
                    "actor_id": actor_name if actor_name else None,
                    "role": message_dict["role"],
                }
            )
        return returned_memories

    # === V3 PHASED BATCH PIPELINE ===

    # Phase 0: Context gathering
    session_scope = _build_session_scope(filters)
    last_messages = memory.db.get_last_messages(session_scope, limit=10)
    parsed_messages = parse_messages(messages)

    # Phase 1: Existing memory retrieval
    search_filters = {k: v for k, v in filters.items() if k in ("user_id", "agent_id", "run_id") and v}
    query_embedding = memory.embedding_model.embed(parsed_messages, "search")
    existing_results = memory.vector_store.search(
        query=parsed_messages,
        vectors=query_embedding,
        top_k=10,
        filters=search_filters,
    )

    # Map UUIDs to integers (anti-hallucination)
    existing_memories = []
    uuid_mapping = {}
    for idx, mem in enumerate(existing_results):
        uuid_mapping[str(idx)] = mem.id
        existing_memories.append({"id": str(idx), "text": mem.payload.get("data", "")})

    # Phase 2: LLM extraction (single call)
    is_agent_scoped = bool(filters.get("agent_id")) and not filters.get("user_id")
    system_prompt = ADDITIVE_EXTRACTION_PROMPT
    if is_agent_scoped:
        system_prompt += AGENT_CONTEXT_SUFFIX

    custom_instr = prompt or memory.custom_instructions

    user_prompt = generate_additive_extraction_prompt(
        existing_memories=existing_memories,
        new_messages=parsed_messages,
        last_k_messages=last_messages,
        custom_instructions=custom_instr,
    )

    try:
        response = memory.llm.generate_response(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
        )
    except Exception as e:
        logger.error(f"LLM extraction failed: {e}")
        return []

    # Parse response
    try:
        response = remove_code_blocks(response)
        if not response or not response.strip():
            extracted_memories = []
        else:
            try:
                extracted_memories = json.loads(response, strict=False).get("memory", [])
            except json.JSONDecodeError:
                extracted_json = extract_json(response)
                extracted_memories = json.loads(extracted_json, strict=False).get("memory", [])
    except Exception as e:
        logger.error(f"Error parsing extraction response: {e}")
        extracted_memories = []

    if not extracted_memories:
        # Save messages even if nothing extracted
        memory.db.save_messages(messages, session_scope)
        return []

    # Phase 3: Batch embed all extracted memory texts
    mem_texts = [m.get("text", "") for m in extracted_memories if m.get("text")]
    try:
        mem_embeddings_list = memory.embedding_model.embed_batch(mem_texts, "add")
        embed_map = dict(zip(mem_texts, mem_embeddings_list))
    except Exception:
        # Fallback: embed individually
        embed_map = {}
        for text in mem_texts:
            try:
                embed_map[text] = memory.embedding_model.embed(text, "add")
            except Exception as e:
                logger.warning(f"Failed to embed memory text: {e}")

    # Phase 4: Per-memory CPU processing + Phase 5: Hash dedup
    # Build set of existing hashes for dedup
    existing_hashes = set()
    for mem in existing_results:
        h = mem.payload.get("hash") if hasattr(mem, "payload") and mem.payload else None
        if h:
            existing_hashes.add(h)

    records = []  # (memory_id, text, embedding, payload)
    seen_hashes = set()  # dedup within the current batch
    for mem in extracted_memories:
        text = mem.get("text")
        if not text or text not in embed_map:
            continue

        mem_hash = hashlib.md5(text.encode()).hexdigest()
        if mem_hash in existing_hashes or mem_hash in seen_hashes:
            logger.debug(f"Skipping duplicate memory (hash match): {text[:50]}")
            continue
        seen_hashes.add(mem_hash)

        text_lemmatized = lemmatize_for_bm25(text)

        memory_id = str(uuid.uuid4())
        mem_metadata = deepcopy(metadata)
        mem_metadata["data"] = text
        mem_metadata["text_lemmatized"] = text_lemmatized
        mem_metadata["hash"] = mem_hash
        if "created_at" not in mem_metadata:
            mem_metadata["created_at"] = datetime.now(timezone.utc).isoformat()
        mem_metadata["updated_at"] = mem_metadata["created_at"]
        if mem.get("attributed_to"):
            mem_metadata["attributed_to"] = mem["attributed_to"]

        records.append((memory_id, text, embed_map[text], mem_metadata))

    if not records:
        memory.db.save_messages(messages, session_scope)
        return []

    # Phase 6: Batch persist
    all_vectors = [r[2] for r in records]
    all_ids = [r[0] for r in records]
    all_payloads = [r[3] for r in records]

    try:
        memory.vector_store.insert(
            vectors=all_vectors,
            ids=all_ids,
            payloads=all_payloads,
        )
    except Exception:
        # Fallback: insert one by one
        for mid, vec, pay in zip(all_ids, all_vectors, all_payloads):
            try:
                memory.vector_store.insert(vectors=[vec], ids=[mid], payloads=[pay])
            except Exception as e:
                logger.error(f"Failed to insert memory {mid}: {e}")

    # Batch history
    history_records = [
        {
            "memory_id": r[0],
            "old_memory": None,
            "new_memory": r[1],
            "event": "ADD",
            "created_at": r[3].get("created_at"),
            "is_deleted": 0,
        }
        for r in records
    ]
    try:
        memory.db.batch_add_history(history_records)
    except Exception:
        # Fallback: add one by one
        for hr in history_records:
            try:
                memory.db.add_history(hr["memory_id"], None, hr["new_memory"], "ADD", created_at=hr.get("created_at"))
            except Exception as e:
                logger.error(f"Failed to add history for {hr['memory_id']}: {e}")

    # Phase 7: Batch entity linking
    try:
        all_texts = [r[1] for r in records]
        all_entities = extract_entities_batch(all_texts)

        # 7a: Global dedup — collect unique entities across all memories
        global_entities = {}  # normalized_key -> (entity_type, entity_text, set of memory_ids)
        for idx, (memory_id, text, embedding, payload) in enumerate(records):
            entities = all_entities[idx] if idx < len(all_entities) else []
            for entity_type, entity_text in entities:
                key = entity_text.strip().lower()
                if key in global_entities:
                    global_entities[key][2].add(memory_id)
                else:
                    global_entities[key] = [entity_type, entity_text, {memory_id}]

        if global_entities:
            ordered_keys = list(global_entities.keys())
            entity_texts = [global_entities[k][1] for k in ordered_keys]

            # 7b: Single batch embed for all unique entities
            try:
                entity_embeddings = memory.embedding_model.embed_batch(entity_texts, "add")
            except Exception:
                # Fallback: embed individually, use None for failures
                entity_embeddings = []
                for t in entity_texts:
                    try:
                        entity_embeddings.append(memory.embedding_model.embed(t, "add"))
                    except Exception:
                        entity_embeddings.append(None)


            if len(entity_embeddings) != len(ordered_keys):
                logger.warning(
                    "embed_batch returned %d vectors for %d entity texts — "
                    "padding/truncating to avoid dropping entity links",
                    len(entity_embeddings),
                    len(ordered_keys),
                )
                entity_embeddings = list(entity_embeddings[: len(ordered_keys)])
                entity_embeddings += [None] * (len(ordered_keys) - len(entity_embeddings))

            # Filter out entities with failed embeddings
            valid = [(i, k) for i, k in enumerate(ordered_keys) if entity_embeddings[i] is not None]
            if valid:
                valid_indices, valid_keys = zip(*valid)
                valid_vectors = [entity_embeddings[i] for i in valid_indices]

                # 7c: Batch search for existing entities
                valid_texts = [global_entities[k][1] for k in valid_keys]
                existing_matches = memory.entity_store.search_batch(
                    queries=valid_texts,
                    vectors_list=valid_vectors,
                    top_k=1,
                    filters=search_filters,
                )

                # 7d: Separate into inserts vs updates
                to_insert_vectors, to_insert_ids, to_insert_payloads = [], [], []
                for j, key in enumerate(valid_keys):
                    entity_type, entity_text, memory_ids = global_entities[key]
                    matches = existing_matches[j] if j < len(existing_matches) else []

                    if matches and matches[0].score >= 0.95:
                        # Update existing entity
                        match = matches[0]
                        payload = match.payload or {}
                        linked = set(payload.get("linked_memory_ids", []))
                        linked |= memory_ids
                        payload["linked_memory_ids"] = sorted(linked)
                        try:
                            memory.entity_store.update(
                                vector_id=match.id,
                                vector=None,
                                payload=payload,
                            )
                        except Exception as e:
                            logger.debug(f"Entity update failed for '{entity_text}': {e}")
                    else:
                        # New entity — collect for batch insert
                        to_insert_vectors.append(valid_vectors[j])
                        to_insert_ids.append(str(uuid.uuid4()))
                        to_insert_payloads.append({
                            "data": entity_text,
                            "entity_type": entity_type,
                            "linked_memory_ids": sorted(memory_ids),
                            **search_filters,
                        })

                # 7e: Single batch insert for all new entities
                if to_insert_vectors:
                    try:
                        memory.entity_store.insert(
                            vectors=to_insert_vectors,
                            ids=to_insert_ids,
                            payloads=to_insert_payloads,
                        )
                    except Exception as e:
                        logger.warning(f"Batch entity insert failed: {e}")
    except Exception as e:
        logger.warning(f"Batch entity linking failed: {e}")

    # Phase 8: Save messages + return
    memory.db.save_messages(messages, session_scope)

    returned_memories = [
        {"id": r[0], "memory": r[1], "event": "ADD"}
        for r in records
    ]

    keys, encoded_ids = process_telemetry_filters(filters)
    capture_event(
        "mem0.add",
        memory,
        {"version": memory.api_version, "keys": keys, "encoded_ids": encoded_ids, "sync_type": "sync"},
    )
    return returned_memories


def create_procedural_memory(memory, messages, metadata=None, prompt=None):
    """
    Create a procedural memory

    Args:
        messages (list): List of messages to create a procedural memory from.
        metadata (dict): Metadata to create a procedural memory from.
        prompt (str, optional): Prompt to use for the procedural memory creation. Defaults to None.
    """
    logger.info("Creating procedural memory")

    parsed_messages = [
        {"role": "system", "content": prompt or PROCEDURAL_MEMORY_SYSTEM_PROMPT},
        *messages,
        {
            "role": "user",
            "content": "Create procedural memory of the above conversation.",
        },
    ]

    try:
        procedural_memory = memory.llm.generate_response(messages=parsed_messages)
        procedural_memory = remove_code_blocks(procedural_memory)
    except Exception as e:
        logger.error(f"Error generating procedural memory summary: {e}")
        raise

    if metadata is None:
        raise ValueError("Metadata cannot be done for procedural memory.")

    metadata = {**metadata, "memory_type": MemoryType.PROCEDURAL.value}
    embeddings = memory.embedding_model.embed(procedural_memory, memory_action="add")
    memory_id = memory._create_memory(procedural_memory, {procedural_memory: embeddings}, metadata=metadata)
    capture_event("mem0._create_procedural_memory", memory, {"memory_id": memory_id, "sync_type": "sync"})

    result = {"results": [{"id": memory_id, "memory": procedural_memory, "event": "ADD"}]}

    return result


async def add_to_vector_store_async(memory, messages, metadata, effective_filters, infer, prompt=None):
    if not infer:
        returned_memories = []
        for message_dict in messages:
            if (
                not isinstance(message_dict, dict)
                or message_dict.get("role") is None
                or message_dict.get("content") is None
            ):
                logger.warning(f"Skipping invalid message format (async): {message_dict}")
                continue

            if message_dict["role"] == "system":
                continue

            per_msg_meta = deepcopy(metadata)
            per_msg_meta["role"] = message_dict["role"]

            actor_name = message_dict.get("name")
            if actor_name:
                per_msg_meta["actor_id"] = actor_name

            msg_content = message_dict["content"]
            msg_embeddings = await asyncio.to_thread(memory.embedding_model.embed, msg_content, "add")
            mem_id = await memory._create_memory(msg_content, {msg_content: msg_embeddings}, per_msg_meta)

            returned_memories.append(
                {
                    "id": mem_id,
                    "memory": msg_content,
                    "event": "ADD",
                    "actor_id": actor_name if actor_name else None,
                    "role": message_dict["role"],
                }
            )
        return returned_memories

    # === V3 PHASED BATCH PIPELINE (async) ===

    # Phase 0: Context gathering
    session_scope = _build_session_scope(effective_filters)
    last_messages = await asyncio.to_thread(memory.db.get_last_messages, session_scope, 10)
    parsed_messages = parse_messages(messages)

    # Phase 1: Existing memory retrieval
    search_filters = {k: v for k, v in effective_filters.items() if k in ("user_id", "agent_id", "run_id") and v}
    query_embedding = await asyncio.to_thread(memory.embedding_model.embed, parsed_messages, "search")
    existing_results = await asyncio.to_thread(
        memory.vector_store.search,
        query=parsed_messages,
        vectors=query_embedding,
        top_k=10,
        filters=search_filters,
    )

    # Map UUIDs to integers (anti-hallucination)
    existing_memories = []
    uuid_mapping = {}
    for idx, mem in enumerate(existing_results):
        uuid_mapping[str(idx)] = mem.id
        existing_memories.append({"id": str(idx), "text": mem.payload.get("data", "")})

    # Phase 2: LLM extraction (single call)
    is_agent_scoped = bool(effective_filters.get("agent_id")) and not effective_filters.get("user_id")
    system_prompt = ADDITIVE_EXTRACTION_PROMPT
    if is_agent_scoped:
        system_prompt += AGENT_CONTEXT_SUFFIX

    custom_instr = prompt or memory.custom_instructions

    user_prompt = generate_additive_extraction_prompt(
        existing_memories=existing_memories,
        new_messages=parsed_messages,
        last_k_messages=last_messages,
        custom_instructions=custom_instr,
    )

    try:
        response = await asyncio.to_thread(
            memory.llm.generate_response,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
        )
    except Exception as e:
        logger.error(f"LLM extraction failed (async): {e}")
        return []

    # Parse response
    try:
        response = remove_code_blocks(response)
        if not response or not response.strip():
            extracted_memories = []
        else:
            try:
                extracted_memories = json.loads(response, strict=False).get("memory", [])
            except json.JSONDecodeError:
                extracted_json = extract_json(response)
                extracted_memories = json.loads(extracted_json, strict=False).get("memory", [])
    except Exception as e:
        logger.error(f"Error parsing extraction response (async): {e}")
        extracted_memories = []

    if not extracted_memories:
        await asyncio.to_thread(memory.db.save_messages, messages, session_scope)
        return []

    # Phase 3: Batch embed all extracted memory texts
    mem_texts = [m.get("text", "") for m in extracted_memories if m.get("text")]
    try:
        mem_embeddings_list = await asyncio.to_thread(memory.embedding_model.embed_batch, mem_texts, "add")
        embed_map = dict(zip(mem_texts, mem_embeddings_list))
    except Exception:
        embed_map = {}
        for text in mem_texts:
            try:
                embed_map[text] = await asyncio.to_thread(memory.embedding_model.embed, text, "add")
            except Exception as e:
                logger.warning(f"Failed to embed memory text (async): {e}")

    # Phase 4: Per-memory CPU processing + Phase 5: Hash dedup
    existing_hashes = set()
    for mem in existing_results:
        h = mem.payload.get("hash") if hasattr(mem, "payload") and mem.payload else None
        if h:
            existing_hashes.add(h)

    records = []
    seen_hashes = set()
    for mem in extracted_memories:
        text = mem.get("text")
        if not text or text not in embed_map:
            continue

        mem_hash = hashlib.md5(text.encode()).hexdigest()
        if mem_hash in existing_hashes or mem_hash in seen_hashes:
            logger.debug(f"Skipping duplicate memory (hash match, async): {text[:50]}")
            continue
        seen_hashes.add(mem_hash)

        text_lemmatized = lemmatize_for_bm25(text)

        memory_id = str(uuid.uuid4())
        mem_metadata = deepcopy(metadata)
        mem_metadata["data"] = text
        mem_metadata["text_lemmatized"] = text_lemmatized
        mem_metadata["hash"] = mem_hash
        if "created_at" not in mem_metadata:
            mem_metadata["created_at"] = datetime.now(timezone.utc).isoformat()
        mem_metadata["updated_at"] = mem_metadata["created_at"]
        if mem.get("attributed_to"):
            mem_metadata["attributed_to"] = mem["attributed_to"]

        records.append((memory_id, text, embed_map[text], mem_metadata))

    if not records:
        await asyncio.to_thread(memory.db.save_messages, messages, session_scope)
        return []

    # Phase 6: Batch persist
    all_vectors = [r[2] for r in records]
    all_ids = [r[0] for r in records]
    all_payloads = [r[3] for r in records]

    try:
        await asyncio.to_thread(
            memory.vector_store.insert,
            vectors=all_vectors,
            ids=all_ids,
            payloads=all_payloads,
        )
    except Exception:
        for mid, vec, pay in zip(all_ids, all_vectors, all_payloads):
            try:
                await asyncio.to_thread(memory.vector_store.insert, vectors=[vec], ids=[mid], payloads=[pay])
            except Exception as e:
                logger.error(f"Failed to insert memory {mid} (async): {e}")

    # Batch history
    history_records = [
        {
            "memory_id": r[0],
            "old_memory": None,
            "new_memory": r[1],
            "event": "ADD",
            "created_at": r[3].get("created_at"),
            "is_deleted": 0,
        }
        for r in records
    ]
    try:
        await asyncio.to_thread(memory.db.batch_add_history, history_records)
    except Exception:
        for hr in history_records:
            try:
                await asyncio.to_thread(
                    memory.db.add_history, hr["memory_id"], None, hr["new_memory"], "ADD",
                    created_at=hr.get("created_at")
                )
            except Exception as e:
                logger.error(f"Failed to add history for {hr['memory_id']} (async): {e}")

    # Phase 7: Batch entity linking
    try:
        all_texts = [r[1] for r in records]
        all_entities = await asyncio.to_thread(extract_entities_batch, all_texts)

        # 7a: Global dedup
        global_entities = {}
        for idx, (memory_id, text, embedding, payload) in enumerate(records):
            entities = all_entities[idx] if idx < len(all_entities) else []
            for entity_type, entity_text in entities:
                key = entity_text.strip().lower()
                if key in global_entities:
                    global_entities[key][2].add(memory_id)
                else:
                    global_entities[key] = [entity_type, entity_text, {memory_id}]

        if global_entities:
            ordered_keys = list(global_entities.keys())
            entity_texts = [global_entities[k][1] for k in ordered_keys]

            # 7b: Batch embed entities
            try:
                entity_embeddings = await asyncio.to_thread(memory.embedding_model.embed_batch, entity_texts, "add")
            except Exception:
                entity_embeddings = []
                for t in entity_texts:
                    try:
                        entity_embeddings.append(await asyncio.to_thread(memory.embedding_model.embed, t, "add"))
                    except Exception:
                        entity_embeddings.append(None)

            if len(entity_embeddings) != len(ordered_keys):
                logger.warning(
                    "embed_batch returned %d vectors for %d entity texts — "
                    "padding/truncating to avoid dropping entity links",
                    len(entity_embeddings),
                    len(ordered_keys),
                )
                entity_embeddings = list(entity_embeddings[: len(ordered_keys)])
                entity_embeddings += [None] * (len(ordered_keys) - len(entity_embeddings))

            valid = [(i, k) for i, k in enumerate(ordered_keys) if entity_embeddings[i] is not None]
            if valid:
                valid_indices, valid_keys = zip(*valid)
                valid_vectors = [entity_embeddings[i] for i in valid_indices]

                # 7c: Batch search for existing entities
                valid_texts = [global_entities[k][1] for k in valid_keys]
                existing_matches = await asyncio.to_thread(
                    memory.entity_store.search_batch,
                    queries=valid_texts,
                    vectors_list=valid_vectors,
                    top_k=1,
                    filters=search_filters,
                )

                # 7d: Separate into inserts vs updates
                to_insert_vectors, to_insert_ids, to_insert_payloads = [], [], []
                for j, key in enumerate(valid_keys):
                    entity_type, entity_text, memory_ids = global_entities[key]
                    matches = existing_matches[j] if j < len(existing_matches) else []

                    if matches and matches[0].score >= 0.95:
                        match = matches[0]
                        payload = match.payload or {}
                        linked = set(payload.get("linked_memory_ids", []))
                        linked |= memory_ids
                        payload["linked_memory_ids"] = sorted(linked)
                        try:
                            await asyncio.to_thread(
                                memory.entity_store.update,
                                vector_id=match.id,
                                vector=None,
                                payload=payload,
                            )
                        except Exception as e:
                            logger.debug(f"Entity update failed for '{entity_text}' (async): {e}")
                    else:
                        to_insert_vectors.append(valid_vectors[j])
                        to_insert_ids.append(str(uuid.uuid4()))
                        to_insert_payloads.append({
                            "data": entity_text,
                            "entity_type": entity_type,
                            "linked_memory_ids": sorted(memory_ids),
                            **search_filters,
                        })

                # 7e: Batch insert new entities
                if to_insert_vectors:
                    try:
                        await asyncio.to_thread(
                            memory.entity_store.insert,
                            vectors=to_insert_vectors,
                            ids=to_insert_ids,
                            payloads=to_insert_payloads,
                        )
                    except Exception as e:
                        logger.warning(f"Batch entity insert failed (async): {e}")
    except Exception as e:
        logger.warning(f"Batch entity linking failed (async): {e}")

    # Phase 8: Save messages + return
    await asyncio.to_thread(memory.db.save_messages, messages, session_scope)

    returned_memories = [
        {"id": r[0], "memory": r[1], "event": "ADD"}
        for r in records
    ]

    keys, encoded_ids = process_telemetry_filters(effective_filters)
    capture_event(
        "mem0.add",
        memory,
        {"version": memory.api_version, "keys": keys, "encoded_ids": encoded_ids, "sync_type": "async"},
    )
    return returned_memories


async def create_procedural_memory_async(memory, messages, metadata=None, llm=None, prompt=None):
    """
    Create a procedural memory asynchronously

    Args:
        messages (list): List of messages to create a procedural memory from.
        metadata (dict): Metadata to create a procedural memory from.
        llm (llm, optional): LLM to use for the procedural memory creation. Defaults to None.
        prompt (str, optional): Prompt to use for the procedural memory creation. Defaults to None.
    """
    try:
        from langchain_core.messages.utils import (
            convert_to_messages,  # type: ignore
        )
    except Exception:
        logger.error(
            "Import error while loading langchain-core. Please install 'langchain-core' to use procedural memory."
        )
        raise

    logger.info("Creating procedural memory")

    parsed_messages = [
        {"role": "system", "content": prompt or PROCEDURAL_MEMORY_SYSTEM_PROMPT},
        *messages,
        {"role": "user", "content": "Create procedural memory of the above conversation."},
    ]

    try:
        if llm is not None:
            parsed_messages = convert_to_messages(parsed_messages)
            response = await asyncio.to_thread(llm.invoke, input=parsed_messages)
            procedural_memory = response.content
        else:
            procedural_memory = await asyncio.to_thread(memory.llm.generate_response, messages=parsed_messages)
            procedural_memory = remove_code_blocks(procedural_memory)
    
    except Exception as e:
        logger.error(f"Error generating procedural memory summary: {e}")
        raise

    if metadata is None:
        raise ValueError("Metadata cannot be done for procedural memory.")

    metadata = {**metadata, "memory_type": MemoryType.PROCEDURAL.value}
    embeddings = await asyncio.to_thread(memory.embedding_model.embed, procedural_memory, memory_action="add")
    memory_id = await memory._create_memory(procedural_memory, {procedural_memory: embeddings}, metadata=metadata)
    capture_event("mem0._create_procedural_memory", memory, {"memory_id": memory_id, "sync_type": "async"})

    result = {"results": [{"id": memory_id, "memory": procedural_memory, "event": "ADD"}]}

    return result

