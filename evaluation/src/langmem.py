import json
import multiprocessing as mp
import os
import time
from collections import defaultdict

from dotenv import load_dotenv
from jinja2 import Template
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import create_react_agent
from langgraph.store.memory import InMemoryStore
from langgraph.utils.config import get_store
from langmem import create_manage_memory_tool, create_search_memory_tool
from openai import OpenAI
from prompts import ANSWER_PROMPT
from tqdm import tqdm

load_dotenv()

client = OpenAI()

ANSWER_PROMPT_TEMPLATE = Template(ANSWER_PROMPT)


def get_answer(question, speaker_1_user_id, speaker_1_memories, speaker_2_user_id, speaker_2_memories):
    prompt = ANSWER_PROMPT_TEMPLATE.render(
        question=question,
        speaker_1_user_id=speaker_1_user_id,
        speaker_1_memories=speaker_1_memories,
        speaker_2_user_id=speaker_2_user_id,
        speaker_2_memories=speaker_2_memories,
    )

    t1 = time.time()
    response = client.chat.completions.create(
        model=os.getenv("MODEL"), messages=[{"role": "system", "content": prompt}], temperature=0.0
    )
    t2 = time.time()
    return response.choices[0].message.content, t2 - t1


def prompt(state):
    """Prepare the messages for the LLM."""
    store = get_store()
    memories = store.search(
        ("memories",),
        query=state["messages"][-1].content,
    )
    system_msg = f"""You are a helpful assistant.

## Memories
<memories>
{memories}
</memories>
"""
    return [{"role": "system", "content": system_msg}, *state["messages"]]


class LangMem:
    def __init__(
        self,
    ):
        self.store = InMemoryStore(
            index={
                "dims": 1536,
                "embed": f"openai:{os.getenv('EMBEDDING_MODEL')}",
            }
        )
        self.checkpointer = MemorySaver()  # Checkpoint graph state

        self.agent = create_react_agent(
            f"openai:{os.getenv('MODEL')}",
            prompt=prompt,
            tools=[
                create_manage_memory_tool(namespace=("memories",)),
                create_search_memory_tool(namespace=("memories",)),
            ],
            store=self.store,
            checkpointer=self.checkpointer,
        )

    def add_memory(self, message, config):
        return self.agent.invoke({"messages": [{"role": "user", "content": message}]}, config=config)

    def search_memory(self, query, config):
        try:
            t1 = time.time()
            response = self.agent.invoke({"messages": [{"role": "user", "content": query}]}, config=config)
            t2 = time.time()
            return response["messages"][-1].content, t2 - t1
        except Exception as e:
            print(f"Error in search_memory: {e}")
            return "", t2 - t1


class LangMemManager:
    def __init__(self, dataset_path):
        self.dataset_path = dataset_path
        with open(self.dataset_path, "r") as f:
            self.data = json.load(f)

    def process_all_conversations(self, output_file_path):
        OUTPUT = defaultdict(list)

        # Process conversations in parallel with multiple workers
        def process_conversation(key_value_pair):
            key, value = key_value_pair
            result = defaultdict(list)

            chat_history = value["conversation"]
            questions = value["question"]

            agent1 = LangMem()
            agent2 = LangMem()
            config = {"configurable": {"thread_id": f"thread-{key}"}}
            speakers = set()

            # Identify speakers
            for conv in chat_history:
                speakers.add(conv["speaker"])

            if len(speakers) != 2:
                raise ValueError(f"Expected 2 speakers, got {len(speakers)}")

            speaker1 = list(speakers)[0]
            speaker2 = list(speakers)[1]

            # Add memories for each message
            for conv in tqdm(chat_history, desc=f"Processing messages {key}", leave=False):
                message = f"{conv['timestamp']} | {conv['speaker']}: {conv['text']}"
                if conv["speaker"] == speaker1:
                    agent1.add_memory(message, config)
                elif conv["speaker"] == speaker2:
                    agent2.add_memory(message, config)
                else:
                    raise ValueError(f"Expected speaker1 or speaker2, got {conv['speaker']}")

            # Process questions
            for q in tqdm(questions, desc=f"Processing questions {key}", leave=False):
                category = q["category"]

                if int(category) == 5:
                    continue

                answer = q["answer"]
                question = q["question"]
                response1, speaker1_memory_time = agent1.search_memory(question, config)
                response2, speaker2_memory_time = agent2.search_memory(question, config)

                generated_answer, response_time = get_answer(question, speaker1, response1, speaker2, response2)

                result[key].append(
                    {
                        "question": question,
                        "answer": answer,
                        "response1": response1,
                        "response2": response2,
                        "category": category,
                        "speaker1_memory_time": speaker1_memory_time,
                        "speaker2_memory_time": speaker2_memory_time,
                        "response_time": response_time,
                        "response": generated_answer,
                    }
                )

            return result

        # Use multiprocessing to process conversations in parallel
        with mp.Pool(processes=10) as pool:
            results = list(
                tqdm(
                    pool.imap(process_conversation, list(self.data.items())),
                    total=len(self.data),
                    desc="Processing conversations",
                )
            )

        # Combine results from all workers
        for result in results:
            for key, items in result.items():
                OUTPUT[key].extend(items)

        # Save final results
        with open(output_file_path, "w") as f:
            json.dump(OUTPUT, f, indent=4)
