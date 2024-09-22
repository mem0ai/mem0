from mem0.configs.prompts import FACT_RETRIEVAL_PROMPT
from mem0.configs.prompts import EXTEND_FACT_RETRIEVAL_PROMPT, OMIT_FACT_RETRIEVAL_PROMPT, RESTRICT_FACT_RETRIEVAL_PROMPT

def get_fact_retrieval_messages(message):
    return FACT_RETRIEVAL_PROMPT, f"Input: {message}"

def get_custom_category_fact_retrieval_messages(custom_category, custom_category_filter, messages):
    if custom_category_filter == "omit":
        return prepare_input_message(custom_category, OMIT_FACT_RETRIEVAL_PROMPT), f"Input: {messages}"
    if custom_category_filter == "restrict":
        return prepare_input_message(custom_category, RESTRICT_FACT_RETRIEVAL_PROMPT), f"Input: {messages}"
    
    return prepare_input_message(custom_category, EXTEND_FACT_RETRIEVAL_PROMPT), f"Input: {messages}"


def parse_messages(messages):
    response = ""
    for msg in messages:
        if msg["role"] == "system":
            response += f"system: {msg['content']}\n"
        if msg["role"] == "user":
            response += f"user: {msg['content']}\n"
        if msg["role"] == "assistant":
            response += f"assistant: {msg['content']}\n"
    return response

def prepare_input_message(custom_category, prompt):
    dict_str = format_custom_categories(custom_category)
    return prompt.replace("CUSTOM_CATEGORIES", dict_str)

def format_custom_categories(custom_category) -> str:
    formatted_strings = []
    for category_dict in custom_category:
        for key, value in category_dict.items():
            formatted_strings.append(f'"{key}": "{value}"')
    
    return "\n".join(formatted_strings)