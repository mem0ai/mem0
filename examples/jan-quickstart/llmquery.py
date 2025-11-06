import os
import requests
import json
from mem0.llms.jan import JanLLM
from mem0.configs.llms.jan import JanConfig

auth_token = "JanServer"
model = "openai_gpt-oss-20b-IQ2_M"
httpheaders = {
    "Authorization": f"Bearer {auth_token}",
    "Content-Type": "application/json",
    "accept": "application/json"
}
url = "http://localhost:1337/v1/chat/completions"

query = {
    "model": model,
    "messages": [
        {
        "role": "user",
        "content": "What is your favorite color?"
        }
    ]
}

response = requests.post(url, data=json.dumps(query), headers=httpheaders)

# Check if the request was successful
if response.status_code == 200:
    # Print the result from the API
    choices = response.json().get("choices")
    first_choice = choices[0]
    result = first_choice["message"]["content"]
    print("Result:", result)
else:
    # Print an error message if the request failed
    print("Error:", response.text)