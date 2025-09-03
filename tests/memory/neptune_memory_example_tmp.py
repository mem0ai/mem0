from mem0 import Memory
import os
import logging
import sys
import boto3
from opensearchpy import RequestsHttpConnection, AWSV4SignerAuth
from dotenv import load_dotenv

load_dotenv()

logging.getLogger("mem0.graphs.neptune.neptunedb").setLevel(logging.DEBUG)
logging.getLogger("mem0.graphs.neptune.base").setLevel(logging.DEBUG)
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

logging.basicConfig(
    format="%(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stdout,  # Explicitly set output to stdout
)

bedrock_embedder_model = "amazon.titan-embed-text-v2:0"
bedrock_llm_model = "us.anthropic.claude-3-7-sonnet-20250219-v1:0"
embedding_model_dims = 1024

neptune_host = os.environ.get("GRAPH_HOST")

opensearch_host = os.environ.get("OS_HOST")
opensearch_port = 443

credentials = boto3.Session().get_credentials()
region = os.environ.get("AWS_REGION")
auth = AWSV4SignerAuth(credentials, region)

config = {
    "embedder": {
        "provider": "aws_bedrock",
        "config": {
            "model": bedrock_embedder_model,
        }
    },
    "llm": {
        "provider": "aws_bedrock",
        "config": {
            "model": bedrock_llm_model,
            "temperature": 0.1,
            "max_tokens": 2000
        }
    },
    "vector_store": {
        "provider": "opensearch",
        "config": {
            "collection_name": "mem0ai_vector_store",
            "host": opensearch_host,
            "port": opensearch_port,
            "http_auth": auth,
            "embedding_model_dims": embedding_model_dims,
            "use_ssl": True,
            "verify_certs": True,
            "connection_class": RequestsHttpConnection,
        },
    },
    "graph_store": {
        "provider": "neptunedb",
        "config": {
            "endpoint": f"neptune-db://{neptune_host}",
        },
    },
}

m = Memory.from_config(config_dict=config)

app_id = "movies"
user_id = "alice"

m.delete_all(user_id=user_id)

#### ADD "I'm planning to watch a movie tonight. Any recommendations?"

messages = [
    {
        "role": "user",
        "content": "Write me a summary of the Empire Strikes Back Starwars movie.",
    },
]

# Store inferred memories (default behavior)
result = m.add(messages, user_id=user_id, metadata={"category": "movie_recommendations"})

all_results = m.get_all(user_id=user_id)
for n in all_results["results"]:
    print(f"node \"{n['memory']}\": [hash: {n['hash']}]")

for e in all_results["relations"]:
    print(f"edge \"{e['source']}\" --{e['relationship']}--> \"{e['target']}\"")

#### ADD "How about a thriller movies? They can be quite engaging."

messages = [
    {
        "role": "assistant",
        "content": "Sure! Here's a concise summary of Star Wars: Episode V – The Empire Strikes Back:",
    },
    {
        "role": "assistant",
        "content": "The Empire Strikes Back (1980) is the second film released in the Star Wars saga and the fifth chronologically.",
    },
    {
        "role": "assistant",
        "content": "After the destruction of the Death Star, the Rebel Alliance is on the run. They’ve set up a base on the icy planet Hoth, but the Empire, led by Darth Vader, quickly locates them and launches an assault. The Rebels are forced to flee.",
    },
    {
        "role": "assistant",
        "content": "Luke Skywalker travels to the remote planet Dagobah to train with Jedi Master Yoda, seeking to become a Jedi Knight. Meanwhile, Han Solo, Princess Leia, Chewbacca, and C-3PO evade Imperial forces and seek refuge in Cloud City, run by Han's old friend Lando Calrissian. However, they’re betrayed, and Han is captured and frozen in carbonite by Vader, who intends to use him as bait for Luke.",
    },
    {
        "role": "assistant",
        "content": "Luke, sensing his friends are in danger, abandons his training and confronts Vader in Cloud City. In a climactic lightsaber duel, Vader defeats Luke and reveals a shocking truth: he is Luke's father. Devastated, Luke escapes with the help of Leia and the others.",
    },
    {
        "role": "assistant",
        "content": "The film ends on a somber note, with the heroes regrouping and preparing to rescue Han and continue the fight against the Empire.",
    },

]

# Store inferred memories (default behavior)
result = m.add(messages, user_id=user_id, metadata={"category": "movie_recommendations"})

all_results = m.get_all(user_id=user_id)
for n in all_results["results"]:
    print(f"node \"{n['memory']}\": [hash: {n['hash']}]")

for e in all_results["relations"]:
    print(f"edge \"{e['source']}\" --{e['relationship']}--> \"{e['target']}\"")

# SEARCH

search_results = m.search("what does alice love?", user_id=user_id)
print("what does alice love?")
for result in search_results["results"]:
    print(f"\"{result['memory']}\" [score: {result['score']}]")
for relation in search_results["relations"]:
    print(f"{relation}")

print("what should we do tonight?")
search_results = m.search("what should we do tonight?", user_id=user_id)
for result in search_results["results"]:
    print(f"\"{result['memory']}\" [score: {result['score']}]")
for relation in search_results["relations"]:
    print(f"{relation}")

# GET ALL

print("all results:")
all_results = m.get_all(user_id=user_id)
print(f"all_results={all_results}")

# TEARDOWN

m.delete_all(user_id)
m.reset()