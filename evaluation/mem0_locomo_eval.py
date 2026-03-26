# =============================================================================
# mem0 LoCoMo Evaluation — 1 Conversation
#
# Uses mem0 repo's own code for everything (prompts, judge, scoring).
# Only adds: Gemini config, ChromaDB, and 1-conversation filter.
#
# Setup:
#   git clone https://github.com/mem0ai/mem0.git
#   cd mem0
#   pip install -e ".[graph]"
#   pip install chromadb google-generativeai
#   place locomo10.json in evaluation/dataset/locomo10.json
#   place this file in evaluation/
#
# Usage:
#   python mem0_locomo_eval.py --mode ingest
#   python mem0_locomo_eval.py --mode evaluate
#   python evals.py --input_file results/mem0_results.json --output_file results/mem0_evals.json
#   python generate_scores.py --input_path results/mem0_evals.json
# =============================================================================

import os
import json
import time
import argparse
from mem0 import Memory

os.environ["GEMINI_API_KEY"] = "AIzaSyAgKhtypq2sSjE8AuLD5-H6eaM6FphQbfs"

CONV_ID        = 0
DATASET_PATH   = "./dataset/locomo10.json"
RESULTS_PATH   = "./results/mem0_results.json"
CHECKPOINT_DIR = "./checkpoints"
SLEEP_SECONDS  = 4    # 15 RPM for gemini-2.5-flash-lite
ERROR_SLEEP    = 30
MODEL_NAME      = "gemini-2.5-flash"  # "gemini-3.1-flash-lite-preview"

# Set True to process only 1 session + 2 questions — quick sanity check
TEST_MODE      = True
CHUNK_SIZE     = 15   # turns per m.add() call — keeps JSON response within token budget
EVAL_LIMIT     = 0    # max questions to evaluate (0 = all)

MEM0_CONFIG = {
    "llm": {
        "provider": "gemini",
        "config": {
            "model": MODEL_NAME,
            "temperature": 0,
            "max_tokens": 4096,  # was 1000 — caused truncated/unterminated JSON
        }
    },
    "embedder": {
        "provider": "gemini",
        "config": {
            "model": "models/gemini-embedding-001",
        }
    },
    "vector_store": {
        "provider": "chroma",
        "config": {
            "collection_name": "locomo_gemini_768",
            "path": "./chroma_db"
        }
    }
}

# =============================================================================
# INGESTION
# =============================================================================

def run_ingest():
    print(f"\n=== Ingestion — conversation {CONV_ID} ===\n")

    os.makedirs(CHECKPOINT_DIR, exist_ok=True)
    os.makedirs("./results", exist_ok=True)

    with open(DATASET_PATH) as f:
        data = json.load(f)

    conv_data    = data[CONV_ID]
    conversation = conv_data["conversation"]
    user_id      = f"user_{CONV_ID}"
    m            = Memory.from_config(MEM0_CONFIG)

    sessions = sorted([
        k for k in conversation
        if k.startswith("session_") and not k.endswith("_date_time")
    ])

    if TEST_MODE:
        sessions = sessions[:1]
        print(f"[TEST MODE] Processing 1 session only\n")

    print(f"Sessions to ingest: {len(sessions)}\n")

    for idx, key in enumerate(sessions):
        checkpoint = os.path.join(CHECKPOINT_DIR, f"{CONV_ID}_{key}.done")

        if os.path.exists(checkpoint):
            print(f"[{idx+1}/{len(sessions)}] {key} — skipping (already done)")
            continue

        session_date = conversation.get(f"{key}_date_time", None)
        print(f"[{idx+1}/{len(sessions)}] {key} | date: {session_date}")

        try:
            raw_session = conversation[key]
            all_messages = [
                {"role": "user", "content": f"{turn['speaker']}: {turn['text']}"}
                for turn in raw_session if "text" in turn
            ]

            # chunk to avoid truncated JSON from long sessions
            chunks = [all_messages[i:i+CHUNK_SIZE] for i in range(0, len(all_messages), CHUNK_SIZE)]
            print(f"  {len(all_messages)} turns → {len(chunks)} chunk(s)")

            for c_idx, chunk in enumerate(chunks):
                m.add(
                    chunk,
                    user_id=user_id,
                    metadata={"session_key": key, "session_date": session_date, "conv_id": CONV_ID}
                )
                print(f"  chunk {c_idx+1}/{len(chunks)} done")
                if c_idx < len(chunks) - 1:
                    time.sleep(SLEEP_SECONDS)

            open(checkpoint, "w").close()
            print(f"  done — sleeping {SLEEP_SECONDS}s\n")
            time.sleep(SLEEP_SECONDS)

        except Exception as e:
            print(f"  error: {e} — sleeping {ERROR_SLEEP}s\n")
            time.sleep(ERROR_SLEEP)

    print("=== Ingestion complete ===")
    print(f"Next: python mem0_locomo_eval.py --mode evaluate\n")


# =============================================================================
# EVALUATION
# Uses mem0's own prompts.py for answer generation.
# Output format matches what mem0's evals.py and generate_scores.py expect.
# =============================================================================

def run_evaluate():
    print(f"\n=== Evaluation — conversation {CONV_ID} ===\n")

    # mem0's own prompt from evaluation/prompts.py
    from prompts import ANSWER_PROMPT

    import google.generativeai as genai
    genai.configure(api_key=os.environ["GEMINI_API_KEY"])
    llm = genai.GenerativeModel(MODEL_NAME)

    with open(DATASET_PATH) as f:
        data = json.load(f)

    conv_data = data[CONV_ID]
    user_id   = f"user_{CONV_ID}"
    m         = Memory.from_config(MEM0_CONFIG)

    # exclude category 5 (adversarial — no ground truth)
    qa_list = [qa for qa in conv_data["qa"] if qa.get("category") != 5]
    if TEST_MODE:
        qa_list = qa_list[:2]
        print(f"[TEST MODE] Evaluating 2 questions only\n")
    elif EVAL_LIMIT > 0:
        qa_list = qa_list[:EVAL_LIMIT]
        print(f"[EVAL_LIMIT] Evaluating {EVAL_LIMIT} questions\n")
    print(f"QA pairs to evaluate: {len(qa_list)}\n")

    results = []

    for i, qa in enumerate(qa_list):
        question = qa["question"]
        answer   = qa["answer"]
        category = qa.get("category", "unknown")

        print(f"[{i+1}/{len(qa_list)}] category={category}")
        print(f"  Q: {question}")
        print(f"  Expected: {answer}")

        # search memories
        try:
            search_results = m.search(question, user_id=user_id)
            memories       = [
                f"{r.get('metadata', {}).get('session_date', '')}: {r['memory']}".lstrip(": ")
                for r in search_results["results"]
            ]
        except Exception as e:
            print(f"  Search error: {e}\n")
            time.sleep(ERROR_SLEEP)
            continue

        time.sleep(SLEEP_SECONDS)

        # generate answer using mem0's own ANSWER_PROMPT
        # ANSWER_PROMPT uses {{double-brace}} placeholders (not Python .format()),
        # and expects two speaker slots. We put all memories under speaker_1.
        memories_str = "\n".join(f"- {mem}" for mem in memories)
        prompt = (
            ANSWER_PROMPT
            .replace("{{speaker_1_user_id}}", user_id)
            .replace("{{speaker_1_memories}}", memories_str)
            .replace("{{speaker_2_user_id}}", "")
            .replace("{{speaker_2_memories}}", "")
            .replace("{{question}}", question)
        )

        try:
            response         = llm.generate_content(prompt)
            generated_answer = response.text.strip()
        except Exception as e:
            print(f"  Generation error: {e}\n")
            generated_answer = "Error generating answer."

        print(f"  Generated: {generated_answer}\n")
        time.sleep(SLEEP_SECONDS)

        # "response" key and dict-of-lists structure matches evals.py expectations
        results.append({
            "question": question,
            "answer":   answer,
            "response": generated_answer,
            "category": category,
            "memories": memories,
            "conv_id":  CONV_ID,
        })

    os.makedirs("./results", exist_ok=True)
    # evals.py expects a dict of lists: {"conv_0": [...]}
    with open(RESULTS_PATH, "w") as f:
        json.dump({f"conv_{CONV_ID}": results}, f, indent=2)

    print(f"=== Evaluation complete ===")
    print(f"Results saved to: {RESULTS_PATH}")
    print(f"\nNext steps:")
    print(f"  python evals.py --input_file {RESULTS_PATH} --output_file results/mem0_evals.json")
    print(f"  python generate_scores.py --input_path results/mem0_evals.json\n")


# =============================================================================
# ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["ingest", "evaluate"], required=True)
    parser.add_argument("--test", action="store_true",
                        help="Test mode: 1 session + 2 questions only")
    parser.add_argument("--eval-limit", type=int, default=0,
                        help="Max questions to evaluate (0 = all)")
    args = parser.parse_args()

    if args.test:
        TEST_MODE = True
        print("[TEST MODE] 1 session, 2 questions\n")
    if args.eval_limit > 0:
        EVAL_LIMIT = args.eval_limit

    if args.mode == "ingest":
        run_ingest()
    elif args.mode == "evaluate":
        run_evaluate()