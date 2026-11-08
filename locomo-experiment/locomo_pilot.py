import argparse
import ast
import hashlib
import json
import logging
import os
import random
import threading
import statistics
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx
import nltk
from nltk.translate.bleu_score import SmoothingFunction, sentence_bleu
from openai import OpenAI

from locomo_providers import PROVIDERS, configure_provider, validate_provider

ROOT = Path(__file__).resolve().parent
nltk.data.path.insert(0, str(ROOT / "nltk_data"))
PAPER = ROOT / "paper-2025" / "evaluation"
DATASET = ROOT / "locomo10.json"
RUN = PROVIDERS["zhizengzeng"].run
MODEL = "gpt-4o-mini"
EMBEDDING_MODEL = "text-embedding-3-small"
USD_TO_CNY = 7.2 * 1.05
ESTIMATED_STOP_CNY = 15
LOCK = threading.RLock()

def literal(path, name):
    for node in ast.parse(path.read_text(encoding="utf-8")).body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == name for t in node.targets):
            return ast.literal_eval(node.value)
    raise ValueError(f"{name} not found in {path}")


INSTRUCTIONS = literal(PAPER / "src/memzero/add.py", "custom_instructions")
ANSWER_PROMPT = literal(PAPER / "prompts.py", "ANSWER_PROMPT")
JUDGE_PROMPT = literal(PAPER / "metrics/llm_judge.py", "ACCURACY_PROMPT")


def save_json(path, value):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temporary, path)


class State:
    def __init__(self, provider):
        provider.run.mkdir(parents=True, exist_ok=True)
        self.path = provider.run / "state.json"
        self.data = json.loads(self.path.read_text()) if self.path.exists() else {
            "provider": provider.name,
            "dataset_sha256": hashlib.sha256(DATASET.read_bytes()).hexdigest(),
            "paper_code_commit": "393a4fd5a6cfeb754857a2229726f567a9fadf36",
            "conversation": 0,
            "completed_ingest": [],
            "inflight_ingest": [],
            "questions": {},
            "usage": {"chat_input": 0, "chat_output": 0, "embedding_input": 0, "responses_without_usage": 0},
        }
        validate_provider(self.data, provider.name)
        if self.data["dataset_sha256"] != hashlib.sha256(DATASET.read_bytes()).hexdigest():
            raise RuntimeError("Dataset has changed since this run was created")
        if self.data["inflight_ingest"]:
            raise RuntimeError(f"Uncertain interrupted writes require manual inspection: {self.data['inflight_ingest']}")
        self.flush()

    def flush(self):
        save_json(self.path, self.data)

    def estimated_cny(self):
        u = self.data["usage"]
        dollars = (u["chat_input"] * 0.15 + u["chat_output"] * 0.60 + u["embedding_input"] * 0.02) / 1_000_000
        return dollars * USD_TO_CNY

    def response_hook(self, response):
        response.read()
        if not response.is_success:
            return
        body = response.json()
        usage = body.get("usage")
        with LOCK:
            if not isinstance(usage, dict):
                self.data["usage"]["responses_without_usage"] += 1
                self.flush()
                raise RuntimeError("API response omitted usage; cost cannot be monitored")
            model = response.request.url.path
            if model.endswith("/embeddings"):
                self.data["usage"]["embedding_input"] += usage["prompt_tokens"]
            elif model.endswith("/chat/completions"):
                self.data["usage"]["chat_input"] += usage["prompt_tokens"]
                self.data["usage"]["chat_output"] += usage["completion_tokens"]
            else:
                raise RuntimeError(f"Unexpected API endpoint: {model}")
            self.flush()

    def check_budget(self):
        with LOCK:
            if self.data["usage"]["responses_without_usage"]:
                raise RuntimeError("API response omitted usage; cost cannot be monitored")
            if self.estimated_cny() >= ESTIMATED_STOP_CNY:
                raise RuntimeError("Estimated local cost reached 15 CNY; check provider billing and budget")

    def start_ingest(self, key):
        with LOCK:
            self.check_budget()
            if key in self.data["completed_ingest"]:
                return False
            self.data["inflight_ingest"].append(key)
            self.flush()
            return True

    def finish_ingest(self, key):
        with LOCK:
            self.data["inflight_ingest"].remove(key)
            self.data["completed_ingest"].append(key)
            self.flush()

    def set_question(self, key, value):
        with LOCK:
            self.data["questions"][str(key)] = value
            self.flush()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider", choices=tuple(PROVIDERS), default="zhizengzeng")
    parser.add_argument("--max-ingest", type=int, default=None, help="Stop after this many additional writes")
    parser.add_argument("--judge-runs", type=int, default=10)
    parser.add_argument("--sample-size", type=int, default=20)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--self-check", action="store_true", help="Validate retrieval, answer and judge without scoring")
    args = parser.parse_args()
    provider, key = configure_provider(args.provider)
    run = provider.run
    state = State(provider)
    if state.data["usage"]["responses_without_usage"]:
        raise RuntimeError("Previous response omitted usage; inspect billing before proceeding")
    http_client = httpx.Client(event_hooks={"response": [state.response_hook]}, timeout=90)
    from mem0 import Memory

    config = {
        "llm": {"provider": "openai", "config": {"model": MODEL, "temperature": 0, "openai_base_url": provider.base_url}},
        "embedder": {"provider": "openai", "config": {"model": EMBEDDING_MODEL, "openai_base_url": provider.base_url}},
        "vector_store": {
            "provider": "qdrant",
            "config": {"collection_name": "locomo", "path": str(run / "qdrant"), "embedding_model_dims": 1536},
        },
        "history_db_path": str(run / "history.db"),
        "custom_instructions": INSTRUCTIONS,
    }
    memory = Memory.from_config(config)
    memory.llm.client = OpenAI(api_key=key, base_url=provider.base_url, http_client=http_client, max_retries=0)
    memory.embedding_model.client = OpenAI(api_key=key, base_url=provider.base_url, http_client=http_client, max_retries=0)
    client = OpenAI(api_key=key, base_url=provider.base_url, http_client=http_client, max_retries=0)

    entry = json.loads(DATASET.read_text(encoding="utf-8"))[0]
    conversation = entry["conversation"]
    speakers = [conversation["speaker_a"], conversation["speaker_b"]]
    if args.self_check:
        question = next(q for q in entry["qa"] if q["category"] == 4)
        found = memory.search(
            question["question"], filters={"user_id": "locomo_0_speaker_0"}, top_k=30
        )["results"]
        response = client.chat.completions.create(
            model=MODEL, temperature=0,
            messages=[{"role": "user", "content": f"Answer briefly: {question['question']}\nMemories: {found}"}],
        )
        prompt = JUDGE_PROMPT.format(
            question=question["question"], gold_answer=question["answer"],
            generated_answer=response.choices[0].message.content,
        )
        judged = client.chat.completions.create(
            model=MODEL, messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}, temperature=0,
        )
        label = json.loads(judged.choices[0].message.content)["label"]
        if label not in ("CORRECT", "WRONG"):
            raise ValueError(f"Unexpected self-check label: {label}")
        print(f"Self-check passed: {len(found)} retrieved, judge={label}; excluded from metrics")
        return
    tasks = []
    for session, turns in conversation.items():
        if not session.startswith("session_") or not isinstance(turns, list):
            continue
        date = conversation[f"{session}_date_time"]
        for i in range(0, len(turns), 2):
            batch = turns[i : i + 2]
            for speaker_index, speaker in enumerate(speakers):
                messages = [
                    {"role": "user" if turn["speaker"] == speaker else "assistant",
                     "content": f"{turn['speaker']}: {turn['text']}"}
                    for turn in batch
                ]
                tasks.append((f"{session}:{i}:{speaker_index}", speaker_index, date, messages))

    pending = [task for task in tasks if task[0] not in state.data["completed_ingest"]]
    if args.max_ingest is not None:
        pending = pending[: args.max_ingest]
    print(f"ingestion remaining={len(pending)} total={len(tasks)}", flush=True)
    stop = threading.Event()

    def ingest_speaker(speaker_index):
        for task_key, _, date, messages in (task for task in pending if task[1] == speaker_index):
            if stop.is_set():
                return
            try:
                if not state.start_ingest(task_key):
                    continue
                result = memory.add(messages, user_id=f"locomo_0_speaker_{speaker_index}", metadata={"timestamp": date})
                state.finish_ingest(task_key)
                print(
                    f"ingested={len(state.data['completed_ingest'])}/{len(tasks)} "
                    f"events={len(result['results'])} estimated_cny={state.estimated_cny():.4f}",
                    flush=True,
                )
            except Exception:
                stop.set()
                raise

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(ingest_speaker, speaker_index) for speaker_index in range(2)]
        for future in futures:
            future.result()
    if len(state.data["completed_ingest"]) != len(tasks):
        print("Ingestion incomplete; no questions evaluated.", flush=True)
        return

    all_questions = [(i, q) for i, q in enumerate(entry["qa"]) if q["category"] == 4]
    if not 1 <= args.sample_size <= len(all_questions):
        raise ValueError(f"sample-size must be between 1 and {len(all_questions)}")
    questions = sorted(random.Random(args.seed).sample(all_questions, args.sample_size))
    sample_path = run / f"sample-{args.sample_size}-seed-{args.seed}.json"
    sample = {
        "conversation": 0, "category": 4, "population": len(all_questions),
        "sample_size": args.sample_size, "seed": args.seed, "question_indices": [i for i, _ in questions],
        "dataset_sha256": state.data["dataset_sha256"],
    }
    if sample_path.exists() and json.loads(sample_path.read_text()) != sample:
        raise RuntimeError("Stored sample does not match the requested sample")
    save_json(sample_path, sample)
    print(f"sample: {sample}", flush=True)
    for index, q in questions:
        result = state.data["questions"].get(str(index))
        if result is None:
            state.check_budget()
            memories = []
            for speaker_index in range(2):
                found = memory.search(
                    q["question"], filters={"user_id": f"locomo_0_speaker_{speaker_index}"}, top_k=30
                )["results"]
                memories.append(found)
            formatted = []
            for group in memories:
                formatted.append(json.dumps([
                    f"{(m.get('metadata') or {}).get('timestamp', 'unknown')}: {m['memory']}"
                    for m in group
                ], indent=4))
            prompt = ANSWER_PROMPT
            for name, value in {
                "speaker_1_user_id": speakers[0],
                "speaker_2_user_id": speakers[1],
                "speaker_1_memories": formatted[0],
                "speaker_2_memories": formatted[1],
                "question": q["question"],
            }.items():
                prompt = prompt.replace("{{" + name + "}}", value)
            response = client.chat.completions.create(
                model=MODEL, messages=[{"role": "system", "content": prompt}], temperature=0
            )
            result = {
                "question": q["question"], "gold": q["answer"], "answer": response.choices[0].message.content,
                "evidence": q.get("evidence", []), "memories": memories, "judgments": [],
            }
            if not result["answer"]:
                raise RuntimeError(f"Empty answer for question {index}")
            state.set_question(index, result)
        while len(result["judgments"]) < args.judge_runs:
            state.check_budget()
            prompt = JUDGE_PROMPT.format(question=q["question"], gold_answer=q["answer"], generated_answer=result["answer"])
            response = client.chat.completions.create(
                model=MODEL, messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"}, temperature=0,
            )
            verdict = json.loads(response.choices[0].message.content)["label"]
            if verdict not in ("CORRECT", "WRONG"):
                raise ValueError(f"Unexpected judge label for question {index}: {verdict}")
            result["judgments"].append(verdict)
            state.set_question(index, result)
        completed_sample = sum(
            len(state.data["questions"].get(str(i), {}).get("judgments", [])) >= args.judge_runs
            for i, _ in questions
        )
        print(f"question={index} completed={completed_sample}/{len(questions)} "
              f"estimated_cny={state.estimated_cny():.4f}", flush=True)

    selected_results = [state.data["questions"][str(index)] for index, _ in questions]
    judgments = [sum(r["judgments"][i] == "CORRECT" for r in selected_results) / len(questions)
                 for i in range(args.judge_runs)]
    f1_scores = []
    bleu_scores = []
    for result in selected_results:
        prediction = str(result["answer"]).strip()
        reference = str(result["gold"]).strip()
        def simple_tokens(text):
            return set(text.lower().replace(".", " ").replace(",", " ").replace("!", " ").replace("?", " ").split())

        pred_tokens = simple_tokens(prediction)
        ref_tokens = simple_tokens(reference)
        common = len(pred_tokens & ref_tokens)
        precision = common / len(pred_tokens) if pred_tokens else 0
        recall = common / len(ref_tokens) if ref_tokens else 0
        f1_scores.append(2 * precision * recall / (precision + recall) if precision + recall else 0)
        bleu_scores.append(sentence_bleu(
            [nltk.word_tokenize(reference.lower())], nltk.word_tokenize(prediction.lower()),
            weights=(1, 0, 0, 0), smoothing_function=SmoothingFunction().method1,
        ))
    summary = {
        "sample": sample, "questions": len(questions), "judge_runs": args.judge_runs, "accuracy_by_run": judgments,
        "judge_mean": statistics.mean(judgments),
        "judge_population_std": statistics.pstdev(judgments),
        "f1": statistics.mean(f1_scores), "bleu1": statistics.mean(bleu_scores),
        "usage": state.data["usage"], "estimated_cny": state.estimated_cny(),
        "note": "Local OSS Mem0, random sample from 1 conversation; not comparable to the hosted full benchmark.",
    }
    save_json(run / f"summary-{args.sample_size}-seed-{args.seed}.json", summary)
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)
    main()
