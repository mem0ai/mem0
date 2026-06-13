"""SAGE memory-eval adapter, mirroring the shape of src/rag.py.

One class with `process_all_conversations(output_file_path)`. For each
conversation in the LoCoMo dataset it (1) seeds every turn into a fresh
per-conversation domain inside a running SAGE node, then (2) for each probe
question hits `/v1/memory/hybrid` to retrieve top-K turns as context and asks
the same gpt-4o-mini prompt the other backends use to produce a short answer.

Output JSON shape is the canonical `{conv_id: [{question, answer, response,
category, context, search_time, response_time, ...}]}` so the existing
`evals.py` LLM-judge step reads it without modification.

Env:
  SAGE_API_URL       REST endpoint of the SAGE node (default http://localhost:18080).
  SAGE_AGENT_KEY     path to an ed25519 priv key; auto-generated ephemeral key if unset.
  MODEL              OpenAI chat model for answer generation (default gpt-4o-mini).
  EMBEDDING_MODEL    OpenAI embedding model (default text-embedding-3-small).
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from collections import defaultdict
from typing import Any

from dotenv import load_dotenv
from jinja2 import Template
from openai import OpenAI
from tqdm import tqdm

try:
    from sage_sdk.auth import AgentIdentity
    from sage_sdk.client import SageClient
except ImportError:
    sys.exit(
        "sage-agent-sdk not installed. Run `pip install sage-agent-sdk>=7.1.0` "
        "or install editable from a SAGE checkout."
    )


PROMPT = """
# Question:
{{QUESTION}}

# Context:
{{CONTEXT}}

# Short answer:
"""

# Bookkeeping markers so the retrieved turn-id can be inspected if needed.
# The visible turn text is preserved exactly so the answer prompt sees the
# same words a RAG baseline would, keeping the comparison fair.
TURN_ID_PREFIX = "[locomo-turn:"
TURN_ID_SUFFIX = "]\n"


class SAGEManager:
    def __init__(
        self,
        data_path: str = "dataset/locomo10.json",
        top_k: int = 10,
    ):
        load_dotenv()
        self.data_path = data_path
        self.top_k = top_k
        self.model = os.getenv("MODEL", "gpt-4o-mini")
        self.embed_model = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
        self.openai = OpenAI()

        sage_url = os.getenv("SAGE_API_URL", "http://localhost:18080")
        agent_key = os.getenv("SAGE_AGENT_KEY", "")
        if agent_key and os.path.isfile(agent_key):
            identity = AgentIdentity.from_file(agent_key)
        else:
            identity = AgentIdentity.generate()
        self.sage = SageClient(base_url=sage_url, identity=identity)

    # ---- embeddings ------------------------------------------------------
    def embed(self, text: str) -> list[float]:
        r = self.openai.embeddings.create(model=self.embed_model, input=text)
        return r.data[0].embedding

    # ---- seeding ---------------------------------------------------------
    def seed_conversation(self, conv_id: str, conversation: dict) -> dict:
        """Seed every turn from one LoCoMo conversation into a fresh SAGE domain.

        Domain is `sage-eval-<conv_id>` so multiple runs don't collide. Turns
        are embedded BEFORE the bookkeeping prefix is added, keeping the
        vector focused on conversation content. The session date is prepended
        to each turn text for parity with mem0's other adapters (RAG/langmem)
        which include the timestamp in their flattened chat history - this
        lets the answer-generation LLM resolve relative time references.
        """
        domain = f"sage-eval-{conv_id}"
        n_seeded = 0
        n_skipped = 0
        t_start = time.time()
        seen_ids: set[str] = set()
        session_re = re.compile(r"^session_(\d+)$")
        for key, value in conversation.items():
            m = session_re.match(key)
            if not m or not isinstance(value, list):
                continue
            session_date = conversation.get(f"{key}_date_time", "")
            for turn in value:
                if not isinstance(turn, dict):
                    continue
                tid = turn.get("dia_id") or turn.get("turn_id") or turn.get("id")
                if not tid or tid in seen_ids:
                    continue
                seen_ids.add(tid)
                speaker = turn.get("speaker") or "?"
                text = (turn.get("text") or "").strip()
                if not text:
                    n_skipped += 1
                    continue
                if session_date:
                    turn_text = f"[{session_date}] {speaker}: {text}"
                else:
                    turn_text = f"{speaker}: {text}"
                content = f"{TURN_ID_PREFIX}{tid}{TURN_ID_SUFFIX}{turn_text}"[:8192]
                try:
                    embedding = self.embed(turn_text)
                    self.sage.propose(
                        content=content,
                        memory_type="observation",
                        domain_tag=domain,
                        confidence=0.85,
                        embedding=embedding,
                    )
                    n_seeded += 1
                except Exception as exc:
                    n_skipped += 1
                    print(f"  ! seed failed for {tid}: {exc}", file=sys.stderr)
        return {
            "domain": domain,
            "n_seeded": n_seeded,
            "n_skipped": n_skipped,
            "seed_seconds": round(time.time() - t_start, 2),
        }

    # ---- search ----------------------------------------------------------
    def search(self, question: str, domain: str) -> tuple[str, float]:
        """Hybrid recall from SAGE; format top-K turns as context for the LLM."""
        t_start = time.time()
        q_embed = self.embed(question)
        results = self.sage.hybrid(
            query=question,
            embedding=q_embed,
            domain_tag=domain,
            top_k=self.top_k,
            status_filter="committed",
        )
        elapsed = time.time() - t_start
        lines: list[str] = []
        for r in results.results:
            content = r.content or ""
            if content.startswith(TURN_ID_PREFIX):
                end = content.find(TURN_ID_SUFFIX, len(TURN_ID_PREFIX))
                if end != -1:
                    content = content[end + len(TURN_ID_SUFFIX):]
            lines.append(content)
        return "\n<->\n".join(lines), elapsed

    # ---- answer generation ----------------------------------------------
    def generate_response(self, question: str, context: str) -> tuple[str, float]:
        """Identical answer prompt to the RAG baseline so the comparison
        measures memory layer quality, not prompt-engineering quality."""
        template = Template(PROMPT)
        prompt = template.render(CONTEXT=context, QUESTION=question)
        max_retries = 3
        retries = 0
        while retries <= max_retries:
            try:
                t1 = time.time()
                response = self.openai.chat.completions.create(
                    model=self.model,
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "You are a helpful assistant that can answer questions "
                                "based on the provided context. If the question involves "
                                "timing, use the conversation date for reference. "
                                "Provide the shortest possible answer. "
                                "Use words directly from the conversation when possible. "
                                "Avoid using subjects in your answer."
                            ),
                        },
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0,
                )
                t2 = time.time()
                return response.choices[0].message.content.strip(), t2 - t1
            except Exception as exc:
                retries += 1
                if retries > max_retries:
                    raise exc
                time.sleep(1)
        return "", 0.0

    # ---- main driver -----------------------------------------------------
    def _load_data(self) -> dict:
        with open(self.data_path) as f:
            raw = json.load(f)
        # mem0's locomo10.json is dict-keyed by conv_id; snap-research's
        # GitHub mirror ships a list of sample dicts. Accept both shapes.
        if isinstance(raw, list):
            return {s.get("sample_id") or s.get("id") or f"conv-{i}": s
                    for i, s in enumerate(raw)}
        return raw

    def process_all_conversations(self, output_file_path: str) -> None:
        data = self._load_data()
        results: dict = defaultdict(list)
        seeds: dict = {}

        for conv_id, sample in tqdm(data.items(), desc="conversations"):
            conversation = sample.get("conversation", {})
            qa_list = sample.get("qa") or sample.get("questions") or []
            if not isinstance(conversation, dict) or not qa_list:
                continue

            seed_info = self.seed_conversation(conv_id, conversation)
            seeds[conv_id] = seed_info
            tqdm.write(
                f"  [seed] {conv_id} turns={seed_info['n_seeded']} "
                f"skipped={seed_info['n_skipped']} in {seed_info['seed_seconds']}s "
                f"-> domain={seed_info['domain']}"
            )

            for qa in tqdm(qa_list, desc=f"qa[{conv_id}]", leave=False):
                question = qa.get("question") or ""
                answer = qa.get("answer", "")
                category = str(qa.get("category", "unknown"))
                if not question.strip():
                    continue

                try:
                    context, search_time = self.search(question, seed_info["domain"])
                    response, response_time = self.generate_response(question, context)
                except Exception as exc:
                    print(f"  ! Q failed conv={conv_id}: {exc}", file=sys.stderr)
                    context, search_time, response, response_time = "", 0.0, "", 0.0

                results[conv_id].append({
                    "question": question,
                    "answer": answer,
                    "category": category,
                    "context": context,
                    "response": response,
                    "search_time": round(search_time, 3),
                    "response_time": round(response_time, 3),
                })
                # Incremental save so a crash mid-run doesn't lose progress.
                with open(output_file_path, "w") as f:
                    json.dump(results, f, indent=2)

        with open(output_file_path, "w") as f:
            json.dump(results, f, indent=2)
        seeds_path = output_file_path.rsplit(".", 1)[0] + ".seeds.json"
        with open(seeds_path, "w") as f:
            json.dump(seeds, f, indent=2)
