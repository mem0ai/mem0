# This example shows how to use vector config to use QDRANT CLOUD
import os

from dotenv import load_dotenv

from mem0 import Memory

# Loading OpenAI API Key
load_dotenv()
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')
USER_ID = "test"
quadrant_host="xx.gcp.cloud.qdrant.io"

# creating the config attributes
collection_name="memory" # this is the collection I created in QDRANT cloud
api_key=os.environ.get("QDRANT_API_KEY") # Getting the QDRANT api KEY
host=quadrant_host
port=6333 #Default port for QDRANT cloud

# Creating the config dict
config = {
    "vector_store": {
        "provider": "qdrant",
        "config": {
            "collection_name": collection_name,
            "host": host,
            "port": port,
            "path": None,
            "api_key":api_key
        }
    }
}

# this is the change, create the memory class using from config
memory = Memory().from_config(config)

USER_DATA = """
I am a strong believer in memory architecture.
"""

response = memory.add(USER_DATA, user_id=USER_ID)
print(response)
