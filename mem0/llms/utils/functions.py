import re

def extract_json(text):
    text = text.strip()
    # Check if it's wrapped in code fences
    match = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL)
    if match:
        json_str = match.group(1)
    else:
        json_str = text  # assume it's raw JSON
    return json_str
