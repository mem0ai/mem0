import json
import os
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

from dotenv import load_dotenv
from jinja2 import Template
from openai import OpenAI
from prompts import ANSWER_PROMPT, ANSWER_PROMPT_GRAPH
from tqdm import tqdm
import random 
from mem0 import Memory

load_dotenv()

# Set the OpenAI API key
os.environ['OPENAI_API_KEY'] = "sk-vyvftxtwuiznrwrfvayhfitxgpdpsykrdnukzfdtdwtjgqvo"
os.environ["OPENAI_BASE_URL"] = "https://api.siliconflow.cn/v1"
model_name = "Qwen/Qwen3-14B"
os.environ["MODEL"] = model_name

config = {
    "llm": {
        "provider": "openai",
        "config": {
            "model": model_name,
            "openai_base_url": "https://api.siliconflow.cn/v1",
            "temperature": 0.1,
            "max_tokens": 2000,
        }
    },
    "embedder": {
        "provider": "openai",
        "config": {
            "model": "BAAI/bge-m3",
            "openai_base_url": "https://api.siliconflow.cn/v1",
        }
    },
    "vector_store": {
        "provider": "qdrant",
        "config": {
            "path": "./qdrant_data/tmp/qdrant_data_locomo1_6",
            "on_disk": True,
            "embedding_model_dims":1024
        }
    },
    "version": "v1.1",
}


class MemorySearch:
    def __init__(self, output_path="results.json", top_k=10, filter_memories=False, is_graph=False):
        self.memory = Memory.from_config(config)
        self.top_k = top_k
        self.openai_client = OpenAI()
        self.results = defaultdict(list)
        self.output_path = output_path
        self.filter_memories = filter_memories
        self.is_graph = is_graph
        self.lock = None
        # self.lock = threading.Lock()

        if self.is_graph:
            self.ANSWER_PROMPT = ANSWER_PROMPT_GRAPH
        else:
            self.ANSWER_PROMPT = ANSWER_PROMPT

    def search_memory(self, user_id, query, max_retries=5, pbar=None):
        start_time = time.time()
        retries = 0
        while retries < max_retries:
            try:
                memories = self.memory.search(
                    query,
                    user_id=user_id,
                    limit=self.top_k,
                )
                break
            except Exception as e:
                pbar.write(f"Retrying search for user {user_id}...{retries+1}/{max_retries}\tError: {str(e)}")
                retries += 1
                if retries >= max_retries:
                    raise e
                time.sleep(random.randint(15, 45))

        end_time = time.time()

        semantic_memories = [
            {
                "memory": memory["memory"],
                "timestamp": memory["metadata"].get("timestamp") if memory.get("metadata") else None,
                "score": round(memory["score"], 2),
            }
            for memory in memories["results"]
        ]
        graph_memories = None

        return semantic_memories, graph_memories, end_time - start_time

    def answer_question(self, speaker_1_user_id, speaker_2_user_id, question, answer, category, pbar=None, max_retries=5):
        speaker_1_memories, speaker_1_graph_memories, speaker_1_memory_time = self.search_memory(
            speaker_1_user_id, question, pbar=pbar
        )
        speaker_2_memories, speaker_2_graph_memories, speaker_2_memory_time = self.search_memory(
            speaker_2_user_id, question, pbar=pbar
        )

        search_1_memory = [f"{item['timestamp']}: {item['memory']}" for item in speaker_1_memories]
        search_2_memory = [f"{item['timestamp']}: {item['memory']}" for item in speaker_2_memories]

        template = Template(self.ANSWER_PROMPT)
        answer_prompt = template.render(
            speaker_1_user_id=speaker_1_user_id.split("_")[0],
            speaker_2_user_id=speaker_2_user_id.split("_")[0],
            speaker_1_memories=json.dumps(search_1_memory, indent=4),
            speaker_2_memories=json.dumps(search_2_memory, indent=4),
            speaker_1_graph_memories=json.dumps(speaker_1_graph_memories, indent=4),
            speaker_2_graph_memories=json.dumps(speaker_2_graph_memories, indent=4),
            question=question,
        )
        for attempt in range(max_retries):
            try:
                t1 = time.time()
                response = self.openai_client.chat.completions.create(
                    model=os.getenv("MODEL"), messages=[{"role": "system", "content": answer_prompt}], temperature=0.0
                )
                t2 = time.time()
                response_time = t2 - t1
                break
            except Exception as e:
                pbar.write(f"\n--- ⚠️ LLM API call failed (Attempt {attempt + 1}/{max_retries}). Retrying... Error: {e} ---\n")
                if attempt < max_retries - 1:
                    time.sleep(random.randint(15, 45))
                else:
                    pbar.write(f"\n--- ❌ [FINAL] LLM call failed permanently for question: '{question[:50]}...' ---\n")
        return (
            response.choices[0].message.content,
            speaker_1_memories,
            speaker_2_memories,
            speaker_1_memory_time,
            speaker_2_memory_time,
            speaker_1_graph_memories,
            speaker_2_graph_memories,
            response_time,
        )

    def process_question(self, val, speaker_a_user_id, speaker_b_user_id, idx, pbar=None, lock=None):
        question = val.get("question", "")
        answer = val.get("answer", "")
        category = val.get("category", -1)
        evidence = val.get("evidence", [])
        adversarial_answer = val.get("adversarial_answer", "")

        (
            response,
            speaker_1_memories,
            speaker_2_memories,
            speaker_1_memory_time,
            speaker_2_memory_time,
            speaker_1_graph_memories,
            speaker_2_graph_memories,
            response_time,
        ) = self.answer_question(speaker_a_user_id, speaker_b_user_id, question, answer, category, pbar)

        result = {
            "question": question,
            "answer": answer,
            "category": category,
            "evidence": evidence,
            "response": response,
            "adversarial_answer": adversarial_answer,
            "speaker_1_memories": speaker_1_memories,
            "speaker_2_memories": speaker_2_memories,
            "num_speaker_1_memories": len(speaker_1_memories),
            "num_speaker_2_memories": len(speaker_2_memories),
            "speaker_1_memory_time": speaker_1_memory_time,
            "speaker_2_memory_time": speaker_2_memory_time,
            "speaker_1_graph_memories": speaker_1_graph_memories,
            "speaker_2_graph_memories": speaker_2_graph_memories,
            "response_time": response_time,
        }


        if lock:
            with lock:
                self.results[idx].append(result)
                with open(self.output_path, "w") as f:
                    json.dump(self.results, f, indent=4)
        else: 
            self.results[idx].append(result)
            with open(self.output_path, "w") as f:
                json.dump(self.results, f, indent=4)
        
        if pbar:
            pbar.update(1)

        return result

    def process_data_file(self, file_path, max_workers=5):
        with open(file_path, "r") as f:
            data = json.load(f)

        total_questions = sum(len(item.get("qa", [])) for item in data)
        if total_questions == 0:
            print("No questions found to process.")
            return
            
        print(f"--- 预计总共需要处理 {total_questions} 个问题 ---")

        successful_count = 0
        failed_count = 0
        
        with tqdm(total=total_questions, desc="💡Total Questions Progress") as pbar:
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = {}
                for idx, item in enumerate(data):
                    qa = item.get("qa", [])
                    conversation = item["conversation"]
                    speaker_a = conversation["speaker_a"]
                    speaker_b = conversation["speaker_b"]
                    speaker_a_user_id = f"{speaker_a}_{idx}"
                    speaker_b_user_id = f"{speaker_b}_{idx}"

                    for question_item in qa:
                        future = executor.submit(
                            self.process_question, 
                            question_item, 
                            speaker_a_user_id, 
                            speaker_b_user_id,
                            idx, 
                            pbar, 
                            self.lock
                        )
                        futures[future] = f"Conv {idx} - Q: {question_item.get('question', '')[:30]}..."

                for future in as_completed(futures):
                    task_id = futures[future]
                    try:
                        future.result() 
                        successful_count += 1
                    except Exception as e:
                        failed_count += 1
                        pbar.write(f"\n--- ❌ Error processing task '{task_id}': {e} ---\n")

        print(f"\n✅ All questions processed. Success: {successful_count}, Failed: {failed_count}")