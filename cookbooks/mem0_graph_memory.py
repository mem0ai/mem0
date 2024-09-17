import os
from mem0 import Memory
from dotenv import load_dotenv
load_dotenv()

config = {
    "llm": {
        "provider": "openai",
        "config": {
            "model": "gpt-4o-mini",
            "temperature": 0
        }
    },
    "graph_store": {
        "provider": "falkordb",
        "config": {
            "host": os.environ['HOST'],
            "username": os.environ['USERNAME'],
            "password": os.environ['PASSWORD'],
            "port": os.environ['PORT']
        }
    },
    "version": "v1.1"
}

m = Memory.from_config(config_dict=config)

user_id = "alice123"
m.add("I like painting", user_id=user_id)
print(m.add("I hate playing badminton", user_id=user_id))
print(m.get_all(user_id=user_id))
m.add("My friend name is john and john has a dog named tommy", user_id='gal')
