"""
Memory Compaction

Provides a way to reduce memory bloat by merging similar memories.

Process:
- Retrieve memories for a given scope
- Group memories that are semantically similar (via embeddings)
- Use the LLM to synthesize one higher-quality, consolidated memory per group
- Replace the originals with the consolidated memory

Key properties:
- Does not affect the hot add path
- Works with any configured LLM and vector store
- Supports dry-run mode
"""

from __future__ import annotations

import json
import logging
import math
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from mem0.configs.base import CompactionConfig
from mem0.configs.prompts import (
    CONSOLIDATION_SYSTEM_PROMPT,
    generate_consolidation_prompt,
)
from mem0.memory.utils import remove_code_blocks

logger = logging.getLogger(__name__)


def _cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
    """Pure-python cosine similarity (fast enough for compaction batches)."""
    if not vec_a or not vec_b or len(vec_a) != len(vec_b):
        return 0.0
    dot = sum(x * y for x, y in zip(vec_a, vec_b))
    na = math.sqrt(sum(x * x for x in vec_a))
    nb = math.sqrt(sum(y * y for y in vec_b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def _get_memory_text(mem: Any) -> str:
    """Extract the canonical memory text from various return shapes."""
    if isinstance(mem, dict):
        return mem.get("memory") or mem.get("data") or mem.get("text") or ""
    payload = getattr(mem, "payload", None) or {}
    if isinstance(payload, dict):
        return payload.get("data") or payload.get("memory") or payload.get("text") or ""
    return getattr(mem, "memory", "") or getattr(mem, "data", "") or str(mem)


def _get_memory_id(mem: Any) -> Optional[str]:
    if isinstance(mem, dict):
        return mem.get("id")
    return getattr(mem, "id", None) or getattr(mem, "memory_id", None)


def _get_payload(mem: Any) -> Dict[str, Any]:
    if isinstance(mem, dict):
        return mem.get("payload", mem.get("metadata", {})) or {}
    return getattr(mem, "payload", {}) or {}


class MemoryCompactor:
    """Core compaction logic. Sensible merge of similar memories via LLM."""

    def __init__(self, memory_instance: Any, config: Optional[CompactionConfig] = None):
        self.memory = memory_instance
        self.config = config or CompactionConfig()
        self.embedder = getattr(memory_instance, "embedding_model", None)
        self.llm = getattr(memory_instance, "llm", None)
        self.vector_store = getattr(memory_instance, "vector_store", None)

    def compact(
        self,
        filters: Dict[str, Any],
        similarity_threshold: Optional[float] = None,
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        """
        Compact similar memories in the given scope.

        - Clusters memories with high embedding similarity
        - Uses LLM to produce one better canonical memory per cluster
        - Replaces the cluster with the merged memory

        Returns a simple report dict.
        """
        start = time.perf_counter()
        threshold = similarity_threshold or self.config.similarity_threshold

        try:
            raw = self.memory.vector_store.list(filters=filters, top_k=100000)
        except Exception as e:
            logger.error(f"list failed during compaction: {e}")
            raise

        memories = self._normalize_memories(raw)
        before = len(memories)

        if before == 0:
            return {"before_count": 0, "after_count": 0, "merges": 0, "dry_run": dry_run}

        texts = [_get_memory_text(m) for m in memories]
        embs = self._embed_texts(texts)
        clusters = self._cluster_by_similarity(memories, embs, threshold, min_size=2)

        added: List[str] = []
        deleted: List[str] = []
        merges = 0
        details = []

        for idxs in clusters:
            if len(idxs) < 2:
                continue
            cluster = [memories[i] for i in idxs]

            cons = self._llm_consolidate(cluster) if self.llm else self._simple_fallback_consolidate(cluster)
            if not cons or not cons.get("memory"):
                continue

            new_text = cons["memory"].strip()
            if len(new_text) < 3:
                continue

            meta = self._build_consolidated_metadata(cluster, cons)

            if dry_run:
                details.append({
                    "size": len(cluster),
                    "consolidated": new_text[:100],
                })
                merges += 1
                continue

            try:
                new_id = self._insert_consolidated(new_text, meta, filters)
                added.append(new_id)
                for m in cluster:
                    mid = _get_memory_id(m)
                    if mid:
                        try:
                            self.vector_store.delete(mid)
                            deleted.append(mid)
                        except Exception:
                            pass
                merges += 1
                details.append({"size": len(cluster), "id": new_id})
            except Exception as e:
                logger.warning(f"Failed to apply merge: {e}")

        after = before - len(deleted) + len(added)
        duration = time.perf_counter() - start

        report = {
            "before_count": before,
            "after_count": max(0, after),
            "merges": merges,
            "dry_run": dry_run,
            "duration": round(duration, 3),
            "details": details,
        }
        logger.info(f"compaction: {before} -> {after} (merges={merges})")
        return report

    # ---------------------- Internal helpers (elegant & robust) ----------------------

    def _normalize_memories(self, raw: Any) -> List[Dict[str, Any]]:
        """Turn vector store list() output into a uniform list of dicts with id + payload."""
        if raw is None:
            return []
        if isinstance(raw, (list, tuple)):
            if raw and isinstance(raw[0], (list, tuple)):
                raw = raw[0]
        normalized = []
        for item in raw or []:
            mid = _get_memory_id(item)
            payload = _get_payload(item)
            text = _get_memory_text(item)
            if not text:
                continue
            normalized.append({
                "id": mid or str(uuid.uuid4()),
                "memory": text,
                "payload": payload,
                "_raw": item,
            })
        return normalized

    def _embed_texts(self, texts: List[str]) -> List[List[float]]:
        """Batch embed using the existing embedder."""
        if not texts:
            return []
        if self.embedder and hasattr(self.embedder, "embed_batch"):
            try:
                return self.embedder.embed_batch(texts, "search") or []
            except Exception:
                pass
        # Fallback individual
        embs = []
        for t in texts:
            try:
                embs.append(self.embedder.embed(t, "search") if self.embedder else [0.0] * 384)
            except Exception:
                embs.append([0.0] * 384)
        return embs

    def _cluster_by_similarity(
        self,
        memories: List[Dict],
        embeddings: List[List[float]],
        threshold: float,
        min_size: int,
    ) -> List[List[int]]:
        """Greedy single-pass clustering. Fast and deterministic enough."""
        n = len(memories)
        if n < min_size:
            return []

        used = [False] * n
        clusters: List[List[int]] = []

        for i in range(n):
            if used[i]:
                continue
            cluster = [i]
            used[i] = True
            for j in range(i + 1, n):
                if used[j]:
                    continue
                sim = _cosine_similarity(embeddings[i], embeddings[j])
                if sim >= threshold:
                    cluster.append(j)
                    used[j] = True
            if len(cluster) >= min_size:
                clusters.append(cluster)
            # else leave them alone (they stay as-is)
        return clusters

    def _llm_consolidate(self, cluster_mems: List[Dict]) -> Optional[Dict[str, Any]]:
        """Call LLM to produce one canonical memory."""
        if not self.llm:
            return self._simple_fallback_consolidate(cluster_mems)

        user_prompt = generate_consolidation_prompt(cluster_mems)

        try:
            resp = self.llm.generate_response(
                messages=[
                    {"role": "system", "content": CONSOLIDATION_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                response_format={"type": "json_object"},
            )
            resp = remove_code_blocks(resp)
            data = json.loads(resp, strict=False)
            if isinstance(data, dict) and data.get("memory"):
                return {
                    "memory": data["memory"],
                    "confidence": float(data.get("confidence", 0.8)),
                    "reason": data.get("reason", ""),
                }
        except Exception as e:
            logger.warning(f"LLM consolidation failed, falling back: {e}")

        return self._simple_fallback_consolidate(cluster_mems)

    def _simple_fallback_consolidate(self, cluster_mems: List[Dict]) -> Dict[str, Any]:
        """Very simple deterministic fallback (concat unique sentences-ish)."""
        seen = set()
        parts = []
        for m in cluster_mems:
            txt = _get_memory_text(m).strip()
            if txt and txt.lower() not in seen:
                parts.append(txt)
                seen.add(txt.lower())
        consolidated = " ".join(parts) if parts else ""
        # Trim if absurdly long
        if len(consolidated) > 600:
            consolidated = consolidated[:597] + "..."
        return {"memory": consolidated, "confidence": 0.6, "reason": "fallback concatenation"}

    def _build_consolidated_metadata(
        self, cluster_mems: List[Dict], consolidated_info: Dict
    ) -> Dict[str, Any]:
        """Craft good metadata for the new memory."""
        now = datetime.now(timezone.utc).isoformat()
        source_count = len(cluster_mems)
        earliest = None
        latest = None
        scopes = set()

        for m in cluster_mems:
            p = _get_payload(m) or {}
            ca = p.get("created_at")
            if ca:
                if earliest is None or ca < earliest:
                    earliest = ca
                if latest is None or ca > latest:
                    latest = ca
            for k in ("user_id", "agent_id", "run_id"):
                if p.get(k):
                    scopes.add(f"{k}={p[k]}")

        meta: Dict[str, Any] = {
            "data": consolidated_info["memory"],
            "consolidated": True,
            "source_count": source_count,
            "consolidated_at": now,
            "consolidation_confidence": consolidated_info.get("confidence", 0.75),
            "consolidation_reason": consolidated_info.get("reason", ""),
        }
        if earliest:
            meta["created_at"] = earliest
        meta["updated_at"] = now

        # Carry over a representative scope (first one is fine; caller already filtered)
        for m in cluster_mems:
            p = _get_payload(m) or {}
            for k in ("user_id", "agent_id", "run_id"):
                if k in p:
                    meta[k] = p[k]
                    break
            break

        return meta

    def _insert_consolidated(
        self, text: str, metadata: Dict[str, Any], filters: Dict[str, Any]
    ) -> str:
        """Insert the new consolidated memory using the same path as normal adds where possible."""
        mem_id = str(uuid.uuid4())
        try:
            # Best path: use the embedder + vector_store.insert directly
            emb = self.embedder.embed(text, "add") if self.embedder else None
            if emb is not None:
                payload = dict(metadata)
                payload.setdefault("data", text)
                self.vector_store.insert(vectors=[emb], ids=[mem_id], payloads=[payload])
            else:
                # Extremely defensive fallback — let the normal add path handle a raw insert
                # (rare)
                self.memory.add([{"role": "user", "content": text}], **{k: v for k, v in filters.items() if k in ("user_id", "agent_id", "run_id")})
                # We won't have the exact id here; return a placeholder
                return mem_id
        except Exception:
            # Last resort: try normal add path
            self.memory.add([{"role": "user", "content": text}], **{k: v for k, v in filters.items() if k in ("user_id", "agent_id", "run_id")})
        return mem_id
