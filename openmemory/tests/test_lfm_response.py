import requests
import json

# python test_lfm_response.py

url = "http://192.168.1.100:1234/v1/chat/completions"

payload = {
    "model": "liquidai_lfm2.5-1.2b-instruct",
    "messages": [
        {
            "role": "system",
            "content": "You are a fact extractor. Extract key facts from the input."
        },
        {
            "role": "user",
            "content": "I am setting up AI locally on my Windows 11 PC. For hardware I have AMD 9950X3D, 32 GB RAM, 5070 TI 16 GB RAM. I have installed LM Studio (LMS) app and installed numerous models from Hugging face for general chat, code chat, and for the VS Code Continue plugin. I have Docker installed. I have installed Open WebUI (OW) and OpenMemory (OM) in Docker. I pulled the mem0 OpenMemory source code from github, modified the code and installed OpenMemory in Docker. I use a specific set of ports for my Docker installed apps in the range of 10000+ in sequence. I modified OpenMemory because most values are baked into the code and I want to use specific local models. I am not using any cloud models. I am using text-embedding-bge-m3 (BGE) and liquidai_lfm2.5-1.2b-instruct (LFM). I use LMS with it's OpenAPI endpoints. I do not use Ollama or the LMS API. I have created an OpenMemory (openmemory or pipe, prefer pipe) pipeline so I can use OpenMemory with Open WebUI. I have custom setups for installing, removing, deploying OW, OM, pipe, etc. I use a docker compose, make file, etc. I will update you on this info when needed."
        }
    ],
    "temperature": 0.1,
    "max_tokens": 300,
    "response_format": {
        "type": "json_schema",
        "json_schema": {
            "name": "memory_extraction",
            "strict": True,
            "schema": {
                "type": "object",
                "properties": {
                    "facts": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of concise atomic facts extracted from the conversation"
                    },
                    "categories": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Relevant categories or tags for the facts"
                    }
                },
                "required": ["facts", "categories"],
                "additionalProperties": False
            }
        }
    }
}

headers = {"Content-Type": "application/json"}

response = requests.post(url, json=payload, headers=headers)

print("Status:", response.status_code)
print("Response:")
print(json.dumps(response.json(), indent=2))