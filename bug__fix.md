# Ensure when using vllm, the <think></think> tags are handled instead of throw an error
### When use vllm like this
```python
import os
from mem0 import Memory

config={
        "vector_store": {
        "provider": "qdrant",
        "config": {
            "collection_name": "test1",
            "host": "localhost",
            "port": 6333,
            "embedding_model_dims": 1024,  
        },
    },
    "embedder":{
        "provider":"huggingface",
        "config":{
            "model":"Qwen/Qwen3-Embedding-0.6B"
        }
    },
    "llm":{
        "provider":"vllm",
        "config":{
            "model":"/mnt/d/AI/Qwen3-4B",
            "vllm_base_url":"http://localhost:8000/v1",
            "temperature":0.1,
            "max_tokens":4096
        }
    }
}
m=Memory.from_config(config)

messages = [
    {"role": "user", "content": "I'm planning to watch a movie tonight. Any recommendations?"},
    {"role": "assistant", "content": "How about thriller movies? They can be quite engaging."},
    {"role": "user", "content": "I'm not a big fan of thrillers, but I love sci-fi movies."},
    {"role": "assistant", "content": "Got it! I'll avoid thrillers and suggest sci-fi movies instead."}
]
m.add(messages, user_id="alice")
m.add("I'm visiting Paris", user_id="john")
memories = m.get_all(user_id="john")
print(memories)
res=m.get_all(user_id="alice")
print(res)
```
- The current implementation in mem0ai/mem0 will throw an error *Error in new_retrieved_facts: Expecting value: line 1 column 1 (char 0)
Error in new_retrieved_facts: Expecting value: line 1 column 1 (char 0)
{'results': []}
{'results': []}*
### What I update
- I directly remove the thinking tags of LLM outputs. Add a function called "remove_thinking_tags" in mem0/
memory/utils.py. Call this function in mem0/memory/main.py.
- And I create a python file "/mem0/tests/memory/test_thinking_tag.py
### Pass the test
- ✅ I ensure my code pass all the test except those skipped because of not setting RUN_TEST_NEPTUNE_ANALYTICS as true and those already marked as not working as expected.
  <img width="1735" height="600" alt="image" src="https://github.com/user-attachments/assets/f9b847c8-d699-42a8-93da-b85580b7e6f7" />
- ✅ I also ensure that pre-commit was installed.
- ✅ Now the code show above can run properly.
### This is my first contribution to the project, and I truly appreciate your time reviewing it!
If there are any issues or suggestions for improvement, I’ll do my best to respond quickly😊.

