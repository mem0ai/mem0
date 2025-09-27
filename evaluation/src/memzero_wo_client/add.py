import json
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from dotenv import load_dotenv
from tqdm import tqdm
from mem0 import Memory
import math
load_dotenv()

# Set the OpenAI API key
os.environ['OPENAI_API_KEY'] = "sk-vyvftxtwuiznrwrfvayhfitxgpdpsykrdnukzfdtdwtjgqvo"
os.environ["OPENAI_BASE_URL"] = "https://api.siliconflow.cn/v1"
model_name = "Qwen/Qwen3-14B"



# Update custom instructions
custom_instructions = """
Generate personal memories that follow these guidelines:

1. Each memory should be self-contained with complete context, including:
   - The person's name, do not use "user" while creating memories
   - Personal details (career aspirations, hobbies, life circumstances)
   - Emotional states and reactions
   - Ongoing journeys or future plans
   - Specific dates when events occurred

2. Include meaningful personal narratives focusing on:
   - Identity and self-acceptance journeys
   - Family planning and parenting
   - Creative outlets and hobbies
   - Mental health and self-care activities
   - Career aspirations and education goals
   - Important life events and milestones

3. Make each memory rich with specific details rather than general statements
   - Include timeframes (exact dates when possible)
   - Name specific activities (e.g., "charity race for mental health" rather than just "exercise")
   - Include emotional context and personal growth elements

4. Extract memories only from user messages, not incorporating assistant responses

5. Format each memory as a paragraph with a clear narrative structure that captures the person's experience, challenges, and aspirations
"""

config = {
    "llm": {
        "provider": "openai",
        "config": {
            "model": model_name,
            "openai_base_url": "https://api.siliconflow.cn/v1",
            "temperature": 0.1,
            "max_tokens": 2000,
            # "prompts": {
            #     "memory_creation": custom_instructions
            # }
        }
    },
    "embedder": {
        "provider": "openai",
        "config": {
            "model": "BAAI/bge-m3",
            "openai_base_url": "https://api.siliconflow.cn/v1",
        }
    },
    # "vector_store": {
    #     "provider": "qdrant",
    #     "config": {
    #         "collection_name": "locomo10",
    #         "embedding_model_dims": 1024,
    #     }
    # },
    "vector_store": {
        "provider": "qdrant",
        "config": {
            "path": "./qdrant_data_locomo1_6",
            "on_disk": True,
            "embedding_model_dims":1024
        }
    },
    "version": "v1.1",
}

import random   

class MemoryADD:
    def __init__(self, data_path=None, batch_size=6, is_graph=False):
        self.memory = Memory.from_config(config)
        self.batch_size = batch_size
        self.data_path = data_path
        self.data = None
        self.is_graph = is_graph
        if data_path:
            self.load_data()

    def load_data(self):
        with open(self.data_path, "r") as f:
            self.data = json.load(f)
        return self.data

    def add_memory(self, user_id, message, metadata, retries=5):
        for attempt in range(retries):
            try:
                _ = self.memory.add(
                    message, user_id=user_id, metadata=metadata
                )
                return
            except Exception as e:
                if attempt < retries - 1:
                    print(f"Retrying...{attempt+1}/{retries}\t{str(e)}")
                    time.sleep(random.randint(20, 60))  # Wait before retrying
                    continue
                else:
                    print("Failed to add memory after retries.", str(e))
                    raise e

    def add_memories_for_speaker(self, speaker, messages, timestamp, desc, pbar=None):
        # for i in range(0, len(messages), self.batch_size):
        for i in tqdm(range(0, len(messages), self.batch_size), desc=desc):
            batch_messages = messages[i : i + self.batch_size]
            self.add_memory(speaker, batch_messages, metadata={"timestamp": timestamp})
            if pbar:
                pbar.update(1)

    def process_conversation(self, item, idx, pbar=None):
        conversation = item["conversation"]
        speaker_a = conversation["speaker_a"]
        speaker_b = conversation["speaker_b"]

        speaker_a_user_id = f"{speaker_a}_{idx}"
        speaker_b_user_id = f"{speaker_b}_{idx}"

        # delete all memories for the two users
        self.memory.delete_all(user_id=speaker_a_user_id)
        self.memory.delete_all(user_id=speaker_b_user_id)

        for key in conversation.keys():
            if key in ["speaker_a", "speaker_b"] or "date" in key or "timestamp" in key:
                continue

            date_time_key = key + "_date_time"
            timestamp = conversation[date_time_key]
            chats = conversation[key]

            messages = []
            messages_reverse = []
            for chat in chats:
                if chat["speaker"] == speaker_a:
                    messages.append({"role": "user", "content": f"{speaker_a}: {chat['text']}"})
                    messages_reverse.append({"role": "assistant", "content": f"{speaker_a}: {chat['text']}"})
                elif chat["speaker"] == speaker_b:
                    messages.append({"role": "assistant", "content": f"{speaker_b}: {chat['text']}"})
                    messages_reverse.append({"role": "user", "content": f"{speaker_b}: {chat['text']}"})
                else:
                    raise ValueError(f"Unknown speaker: {chat['speaker']}")

            # add memories for the two users on different threads
            # thread_a = threading.Thread(
            #     target=self.add_memories_for_speaker,
            #     args=(speaker_a_user_id, messages, timestamp, "Adding Memories for Speaker A", pbar),
            # )
            # thread_b = threading.Thread(
            #     target=self.add_memories_for_speaker,
            #     args=(speaker_b_user_id, messages_reverse, timestamp, "Adding Memories for Speaker B", pbar),
            # )

            # thread_a.start()
            # thread_b.start()
            # thread_a.join()
            # thread_b.join()
           
            self.add_memories_for_speaker(speaker_a_user_id, messages, timestamp, "Adding Memories for Speaker A", pbar)
            self.add_memories_for_speaker(speaker_b_user_id, messages_reverse, timestamp, "Adding Memories for Speaker B", pbar)
        
        print("Messages added successfully")

    # def process_all_conversations(self, max_workers=4):
    #     if not self.data:
    #         raise ValueError("No data loaded. Please set data_path and call load_data() first.")
    #     with ThreadPoolExecutor(max_workers=max_workers) as executor:
    #         futures = [executor.submit(self.process_conversation, item, idx) for idx, item in enumerate(self.data)]

    #         for future in futures:
    #             future.result()

    def process_all_conversations(self, max_workers=6):
        if not self.data:
            raise ValueError("No data loaded. Please set data_path and call load_data() first.")
        total_batches = 0
        for item in self.data:
            conversation = item["conversation"]
            for key in conversation.keys():
                if key in ["speaker_a", "speaker_b"] or "date" in key or "timestamp" in key:
                    continue
                
                num_messages = len(conversation[key])
                # 每个对话轮次，A和B都要处理一次，所以计算两次
                batches_for_speaker_a = math.ceil(num_messages / self.batch_size)
                batches_for_speaker_b = math.ceil(num_messages / self.batch_size)
                total_batches += batches_for_speaker_a + batches_for_speaker_b
        
        print(f"--- 预计总共需要处理 {total_batches} 个批次 ---")


        successful_count = 0
        failed_count = 0
        
        with tqdm(total=total_batches, desc="💡Total Batch Progress") as pbar:
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = {
                    executor.submit(self.process_conversation, item, idx, pbar): f"Conversation {idx}" 
                    for idx, item in enumerate(self.data)
                }

                for future in as_completed(futures):
                    conversation_id = futures[future]
                    try:
                        future.result()
                        successful_count += 1
                    except Exception as e:
                        failed_count += 1
                        pbar.write(f"\n---[retry{failed_count}] ❌ Error processing {conversation_id}: {e} ---\n")

        print(f"\n✅ All conversations processed. Success: {successful_count}, Failed: {failed_count}")