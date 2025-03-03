import re
from mem0.configs.prompts import FACT_RETRIEVAL_PROMPT
from mem0.llms.openai import OpenAILLM


def get_fact_retrieval_messages(message):
    return FACT_RETRIEVAL_PROMPT, f"Input:\n{message}"


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


def format_entities(entities):
    if not entities:
        return ""

    formatted_lines = []
    for entity in entities:
        simplified = f"{entity['source']} -- {entity['relatationship']} -- {entity['destination']}"
        formatted_lines.append(simplified)

    return "\n".join(formatted_lines)


def remove_code_blocks(content: str) -> str:
    """
    Removes enclosing code block markers ```[language] and ``` from a given string.

    Remarks:
    - The function uses a regex pattern to match code blocks that may start with ``` followed by an optional language tag (letters or numbers) and end with ```.
    - If a code block is detected, it returns only the inner content, stripping out the markers.
    - If no code block markers are found, the original content is returned as-is.
    """
    pattern = r"^```[a-zA-Z0-9]*\n([\s\S]*?)\n```$"
    match = re.match(pattern, content.strip())
    return match.group(1).strip() if match else content.strip()


def get_image_description(image_url):
    """
    Get the description of the image
    """
    llm = OpenAILLM()
    response = llm.generate_response(
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "Provide a description of the image and do not include any additional text.",
                    },
                    {"type": "image_url", "image_url": {"url": image_url}},
                ],
            },
        ],
        max_tokens=100,
    )
    return response


def parse_vision_messages(messages):
    """
    Parse the vision messages from the messages
    """
    returned_messages = []
    for msg in messages:
        if msg["role"] != "system":
            if not isinstance(msg["content"], str) and msg["content"]["type"] == "image_url":
                image_url = msg["content"]["image_url"]["url"]
                try:
                    description = get_image_description(image_url)
                    msg["content"]["text"] = description
                    returned_messages.append({"role": msg["role"], "content": description})
                except Exception:
                    raise Exception(f"Error while downloading {image_url}.")
            else:
                returned_messages.append(msg)
        else:
            returned_messages.append(msg)
    return returned_messages
