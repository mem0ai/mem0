"""Minimal AG2 (formerly AutoGen) + Mem0 example."""

import os
from mem0 import MemoryClient
from autogen import ConversableAgent


def build_agent() -> ConversableAgent:
    return ConversableAgent(
        "memory_agent",
        llm_config={
            "config_list": [
                {"model": "gpt-4", "api_key": os.environ.get("OPENAI_API_KEY")}
            ]
        },
        code_execution_config=False,
        human_input_mode="NEVER",
    )


def main() -> None:
    os.environ.setdefault("OPENAI_API_KEY", "your-openai-api-key")
    os.environ.setdefault("MEM0_API_KEY", "your-mem0-api-key")

    memory = MemoryClient()
    agent = build_agent()
    user_id = "example_user"

    question = "What do you remember about my preferences?"

    memories = memory.search(question, user_id=user_id)
    results = memories.get("results", [])
    context = "\n".join([f"- {item['memory']}" for item in results])

    prompt = f"""Answer the user question using relevant memories.
Memories:
{context}

Question: {question}
"""

    reply = agent.generate_reply(messages=[{"role": "user", "content": prompt}])
    print(reply)

    memory.add(
        [
            {"role": "user", "content": question},
            {"role": "assistant", "content": reply},
        ],
        user_id=user_id,
    )


if __name__ == "__main__":
    main()
