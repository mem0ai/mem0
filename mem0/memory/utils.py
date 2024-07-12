from mem0.configs.prompts import UPDATE_MEMORY_PROMPT


def get_update_memory_prompt(existing_memories, memory, template=UPDATE_MEMORY_PROMPT):
    return template.format(existing_memories=existing_memories, memory=memory)


def get_update_memory_messages(existing_memories, memory):
    return [
        {
            "role": "user",
            "content": get_update_memory_prompt(existing_memories, memory),
        },
    ]
