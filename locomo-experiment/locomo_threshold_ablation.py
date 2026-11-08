import argparse
import hashlib
import json
import statistics
import threading
import time

import httpx
import nltk
import tiktoken
from nltk.translate.bleu_score import SmoothingFunction, sentence_bleu
from openai import OpenAI

from locomo_pilot import (
    ANSWER_PROMPT,
    DATASET,
    EMBEDDING_MODEL,
    INSTRUCTIONS,
    JUDGE_PROMPT,
    MODEL,
    RUN,
    USD_TO_CNY,
    save_json,
)
from locomo_providers import PROVIDERS, configure_provider, validate_provider

BASELINE = RUN / "state.json"
SAMPLE = RUN / "sample-70-seed-42.json"
JUDGE_RUNS = 10
LOCK = threading.RLock()
MAX_ESTIMATED_CNY = 3.0
ENCODING = tiktoken.encoding_for_model(MODEL)


def cost(input_tokens, output_tokens, embedding_tokens=0):
    return USD_TO_CNY * (0.15 * input_tokens + 0.60 * output_tokens + 0.02 * embedding_tokens) / 1_000_000


def make_prompt(question, memories, speakers):
    prompt = ANSWER_PROMPT
    fields = {
        "speaker_1_user_id": speakers[0],
        "speaker_2_user_id": speakers[1],
        "question": question,
    }
    for index, group in enumerate(memories, 1):
        fields[f"speaker_{index}_memories"] = json.dumps([
            f"{(item.get('metadata') or {}).get('timestamp', 'unknown')}: {item['memory']}"
            for item in group
        ], indent=4)
    for name, value in fields.items():
        prompt = prompt.replace("{{" + name + "}}", value)
    return prompt


def answer_usage_estimate(prompt, answer):
    # gpt-4o chat framing: three tokens per message, one reply primer.
    # Provider-side framing and hidden accounting may differ.
    return {
        "input_tokens": len(ENCODING.encode(prompt)) + len(ENCODING.encode("system")) + 6,
        "output_tokens": len(ENCODING.encode(answer)),
    }


def answer_usage_totals(results, speakers):
    estimates = [
        answer_usage_estimate(make_prompt(item["question"], item["memories"], speakers), item["answer"])
        for item in results
    ]
    return {
        "input_tokens": sum(item["input_tokens"] for item in estimates),
        "output_tokens": sum(item["output_tokens"] for item in estimates),
        "method": "tiktoken model encoding plus estimated chat framing; not billed usage",
    }


def lexical_scores(prediction, reference):
    prediction = str(prediction).strip()
    reference = str(reference).strip()

    def tokens(text):
        return set(text.lower().replace(".", " ").replace(",", " ").replace("!", " ").replace("?", " ").split())

    pred_tokens, ref_tokens = tokens(prediction), tokens(reference)
    common = len(pred_tokens & ref_tokens)
    precision = common / len(pred_tokens) if pred_tokens else 0
    recall = common / len(ref_tokens) if ref_tokens else 0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0
    bleu = sentence_bleu(
        [nltk.word_tokenize(reference.lower())], nltk.word_tokenize(prediction.lower()),
        weights=(1, 0, 0, 0), smoothing_function=SmoothingFunction().method1,
    )
    return f1, bleu


def metrics(results):
    scores = [lexical_scores(result["answer"], result["gold"]) for result in results]
    judges = [
        sum(item["judgments"][run] == "CORRECT" for item in results) / len(results)
        for run in range(JUDGE_RUNS)
    ]
    return {
        "f1": statistics.mean(score[0] for score in scores),
        "bleu1": statistics.mean(score[1] for score in scores),
        "judge_mean": statistics.mean(judges),
        "judge_population_std": statistics.pstdev(judges),
        "judge_by_run": judges,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-questions", type=int, default=70)
    parser.add_argument("--provider", choices=tuple(PROVIDERS), default="zhizengzeng")
    parser.add_argument("--experiment", choices=("threshold05",), default="threshold05")
    args = parser.parse_args()
    if not 1 <= args.max_questions <= 70:
        parser.error("--max-questions must be between 1 and 70")
    provider = PROVIDERS[args.provider]
    run = provider.run
    baseline_path = run / "state.json"
    sample_path = run / "sample-70-seed-42.json"
    top_k, threshold = 30, 0.5
    output = run / "threshold05-ablation"
    dataset_hash = hashlib.sha256(DATASET.read_bytes()).hexdigest()
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    validate_provider(baseline, provider.name)
    sample = json.loads(sample_path.read_text(encoding="utf-8"))
    if baseline["dataset_sha256"] != dataset_hash or sample["dataset_sha256"] != dataset_hash:
        raise RuntimeError("Dataset does not match the baseline")
    ids = sample["question_indices"]
    if len(ids) != 70 or len(set(ids)) != 70 or baseline["inflight_ingest"]:
        raise RuntimeError("Baseline is incomplete or sample is invalid")
    entry = json.loads(DATASET.read_text(encoding="utf-8"))[0]
    expected_ids = [i for i, question in enumerate(entry["qa"]) if question["category"] == 4]
    if ids != expected_ids:
        raise RuntimeError("Sample does not match all 70 single-hop questions")
    for i in ids:
        result = baseline["questions"][str(i)]
        if result["question"] != entry["qa"][i]["question"] or len(result["judgments"]) != JUDGE_RUNS:
            raise RuntimeError(f"Baseline question {i} is incomplete or mismatched")

    output.mkdir(exist_ok=True)
    state_path = output / "state.json"
    initial = {
        "dataset_sha256": dataset_hash, "top_k": top_k, "threshold": threshold, "question_indices": ids,
        "baseline_sha256": hashlib.sha256(baseline_path.read_bytes()).hexdigest(),
        "provider": provider.name,
        "judge_runs": JUDGE_RUNS, "questions": {},
        "usage_by_phase": {
            phase: {"input_tokens": 0, "output_tokens": 0, "embedding_tokens": 0, "calls": 0}
            for phase in ("search", "answer", "judge")
        },
        "responses_without_usage": 0,
    }
    state = json.loads(state_path.read_text()) if state_path.exists() else initial
    validate_provider(state, provider.name)
    for field in ("dataset_sha256", "top_k", "threshold", "question_indices", "baseline_sha256", "judge_runs"):
        if state[field] != initial[field]:
            raise RuntimeError(f"Existing experiment differs in {field}")
    if state["responses_without_usage"]:
        raise RuntimeError("A previous response lacked usage; inspect billing before continuing")
    save_json(state_path, state)

    active_phase = None

    def estimated_cost():
        return sum(cost(u["input_tokens"], u["output_tokens"], u["embedding_tokens"])
                   for u in state["usage_by_phase"].values())

    def check_budget():
        if state["responses_without_usage"] or estimated_cost() >= MAX_ESTIMATED_CNY:
            raise RuntimeError("Estimated cost cap reached or usage is unavailable; stop and inspect billing")

    def response_hook(response):
        response.read()
        if not response.is_success:
            return
        body = response.json()
        usage = body.get("usage")
        with LOCK:
            if not isinstance(usage, dict):
                state["responses_without_usage"] += 1
                save_json(state_path, state)
                raise RuntimeError("API response omitted usage")
            phase = active_phase
            if phase not in state["usage_by_phase"]:
                raise RuntimeError("Unexpected untracked API call")
            bucket = state["usage_by_phase"][phase]
            if response.request.url.path.endswith("/embeddings"):
                bucket["embedding_tokens"] += usage["prompt_tokens"]
            elif response.request.url.path.endswith("/chat/completions"):
                bucket["input_tokens"] += usage["prompt_tokens"]
                bucket["output_tokens"] += usage["completion_tokens"]
            else:
                raise RuntimeError(f"Unexpected endpoint {response.request.url.path}")
            bucket["calls"] += 1
            save_json(state_path, state)

    provider, key = configure_provider(args.provider)
    http = httpx.Client(event_hooks={"response": [response_hook]}, timeout=90)
    client = OpenAI(api_key=key, base_url=provider.base_url, http_client=http, max_retries=0)
    from mem0 import Memory

    memory = Memory.from_config({
        "llm": {"provider": "openai", "config": {"model": MODEL, "temperature": 0, "openai_base_url": provider.base_url}},
        "embedder": {"provider": "openai", "config": {"model": EMBEDDING_MODEL, "openai_base_url": provider.base_url}},
        "vector_store": {
            "provider": "qdrant",
            "config": {"collection_name": "locomo", "path": str(run / "qdrant"), "embedding_model_dims": 1536},
        },
        "history_db_path": str(run / "history.db"),
        "custom_instructions": INSTRUCTIONS,
    })
    memory.llm.client = client
    memory.embedding_model.client = client
    speakers = [entry["conversation"]["speaker_a"], entry["conversation"]["speaker_b"]]
    start = time.perf_counter()
    for i in ids[:args.max_questions]:
        question = entry["qa"][i]
        result = state["questions"].get(str(i))
        if result is None:
            check_budget()
            active_phase = "search"
            t = time.perf_counter()
            memories = [
                memory.search(
                    question["question"], filters={"user_id": f"locomo_0_speaker_{speaker}"},
                    top_k=top_k, threshold=threshold, explain=True,
                )["results"]
                for speaker in range(2)
            ]
            retrieval_seconds = time.perf_counter() - t
            if any(len(group) > top_k for group in memories):
                raise RuntimeError(f"Search exceeded top-k for question {i}")
            for group in memories:
                for item in group:
                    details = item["score_details"]
                    if details["semantic_score"] < threshold or details["threshold"] != threshold:
                        raise RuntimeError(f"Search returned a memory below the threshold for question {i}")
            prompt = make_prompt(question["question"], memories, speakers)
            active_phase = "answer"
            check_budget()
            t = time.perf_counter()
            response = client.chat.completions.create(
                model=MODEL, messages=[{"role": "system", "content": prompt}], temperature=0
            )
            answer_seconds = time.perf_counter() - t
            answer = response.choices[0].message.content
            if not answer:
                raise RuntimeError(f"Empty answer for question {i}")
            usage = response.usage
            if usage is None:
                raise RuntimeError(f"Missing answer usage for question {i}")
            result = {
                "question": question["question"], "gold": question["answer"], "answer": answer,
                "evidence": question.get("evidence", []), "memories": memories, "judgments": [],
                "retrieval_seconds": retrieval_seconds, "answer_seconds": answer_seconds,
                "answer_usage": {"input_tokens": usage.prompt_tokens, "output_tokens": usage.completion_tokens},
            }
            state["questions"][str(i)] = result
            save_json(state_path, state)
        while len(result["judgments"]) < JUDGE_RUNS:
            check_budget()
            active_phase = "judge"
            prompt = JUDGE_PROMPT.format(
                question=question["question"], gold_answer=question["answer"], generated_answer=result["answer"]
            )
            response = client.chat.completions.create(
                model=MODEL, messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"}, temperature=0,
            )
            label = json.loads(response.choices[0].message.content)["label"]
            if label not in ("CORRECT", "WRONG"):
                raise ValueError(f"Unexpected judge label for question {i}: {label}")
            result["judgments"].append(label)
            save_json(state_path, state)
        completed = sum(len(item["judgments"]) == JUDGE_RUNS for item in state["questions"].values())
        print(f"question={i} completed={completed}/70 cost_estimate={estimated_cost():.4f} "
              f"elapsed={time.perf_counter() - start:.0f}s", flush=True)

    if len(state["questions"]) != 70 or any(len(item["judgments"]) != JUDGE_RUNS for item in state["questions"].values()):
        print("Partial run; no final comparison produced.")
        return
    base_results = [baseline["questions"][str(i)] for i in ids]
    new_results = [state["questions"][str(i)] for i in ids]
    baseline_estimate = answer_usage_totals(base_results, speakers)
    experiment_estimate = answer_usage_totals(new_results, speakers)
    actual = state["usage_by_phase"]["answer"]
    actual_cost = cost(actual["input_tokens"], actual["output_tokens"])
    baseline_estimated_cost = cost(baseline_estimate["input_tokens"], baseline_estimate["output_tokens"])
    summary = {
        "questions": 70, "provider": provider.name, "shared_memory_store": f"{run.name}/qdrant",
        "baseline_top_k": 30, "baseline_threshold": 0.1,
        "experiment_top_k": top_k, "experiment_threshold": threshold,
        "baseline_metrics": metrics(base_results), "experiment_metrics": metrics(new_results),
        "baseline_memory_count": sum(len(group) for item in base_results for group in item["memories"]),
        "experiment_memory_count": sum(len(group) for item in new_results for group in item["memories"]),
        "empty_speaker_retrievals": sum(not group for item in new_results for group in item["memories"]),
        "baseline_answer_usage_estimated": {
            **baseline_estimate,
            "estimated_cny": baseline_estimated_cost,
        },
        "experiment_answer_usage_estimated": experiment_estimate,
        "answer_input_token_change_vs_estimated_baseline": (
            experiment_estimate["input_tokens"] / baseline_estimate["input_tokens"] - 1
        ),
        "answer_output_token_change_vs_estimated_baseline": (
            experiment_estimate["output_tokens"] / baseline_estimate["output_tokens"] - 1
        ),
        "experiment_usage_by_phase": state["usage_by_phase"],
        "experiment_answer_estimated_cny_from_api_usage": actual_cost,
        "experiment_total_estimated_cny_from_api_usage": estimated_cost(),
        "answer_cost_change_vs_estimated_baseline": (actual_cost / baseline_estimated_cost - 1),
        "experiment_mean_retrieval_seconds": statistics.mean(r["retrieval_seconds"] for r in new_results),
        "experiment_mean_answer_seconds": statistics.mean(r["answer_seconds"] for r in new_results),
        "baseline_latency_available": False,
        "note": "Same question set and store; answer tokens reconstructed for both groups; costs are estimates; no causal timing comparison.",
    }
    save_json(output / "summary.json", summary)
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == "__main__":
    main()
