"""Pre-load the Ollama embedding model before uvicorn starts."""
import json
import os
import sys
import time
import urllib.request

model = os.environ.get("EMBEDDING_MODEL", "nomic-embed-text-v2-moe")
base_url = os.environ.get("OLLAMA_BASE_URL", "http://host.docker.internal:11434")
url = f"{base_url}/api/embed"
payload = json.dumps({"model": model, "input": "warmup", "keep_alive": -1}).encode()

for attempt in range(1, 6):
    try:
        req = urllib.request.Request(
            url, data=payload, headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=60) as r:
            r.read()
        print(f"Embedding model ready: {model} (keep_alive=-1)")
        sys.exit(0)
    except Exception as e:
        print(f"Attempt {attempt}/5 failed: {e}", file=sys.stderr)
        if attempt < 5:
            time.sleep(2)

print("ERROR: could not warm up embedding model after 5 attempts", file=sys.stderr)
sys.exit(1)
