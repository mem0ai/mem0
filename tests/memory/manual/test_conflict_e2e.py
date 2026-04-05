import os
from mem0 import Memory

config = {
    "llm": {
        "provider": "openai",
        "config": {"model": "gpt-4o-mini"}
    },
    "conflict_detection": {
        "similarity_threshold": 0.70, # reduce from 0.85
    }
}

m = Memory.from_config(config)

USER = "alice"

# Add a baseline memory
m.add("I live in New York City", user_id = USER)
print("After first add: ", m.get_all(user_id = USER))

# KEEP HIGHER CONFIDENCE TEST
# Add a contradiction -- should trigger autoresolve (DEFAULT - keep higher confidence)
m.add("I moved to San Francisco last month.", user_id = USER)
print("After contradiction: ", m.get_all(user_id = USER))

