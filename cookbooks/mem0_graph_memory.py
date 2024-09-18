# This example shows how to use graph config to use falkordb graph databese
import os
from mem0 import Memory
from dotenv import load_dotenv

# Loading OpenAI API Key
load_dotenv()
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')
USER_ID = "test"

# Creating the config dict from the environment variables
config = {
    "llm": { # This is the language model configuration, use your carditionals
        "provider": "openai",
        "config": {
            "model": "gpt-4o-mini",
            "temperature": 0
        }
    },
    "graph_store": { # See https://app.falkordb.cloud/ for the carditionals
        "provider": "falkordb",
        "config": {
            "host": os.environ['HOST'],
            "username": os.environ['USERNAME'],# if you are using local host, the username and password will not be needed
            "password": os.environ['PASSWORD'],
            "port": os.environ['PORT']
        }
    },
    "version": "v1.1"
}

# Create the memory class using from config
memory = Memory.from_config(config_dict=config)

# Use the Mem0 to add and search memories
memory.add("I like painting", user_id=USER_ID)
memory.add("I hate playing badminton", user_id=USER_ID)
print(memory.get_all(user_id=USER_ID))
memory.add("My friend name is john and john has a dog named tommy", user_id=USER_ID)
print(memory.search("What I like to do", user_id=USER_ID))
