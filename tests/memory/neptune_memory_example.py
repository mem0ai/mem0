from mem0 import Memory
import os
import logging
import sys
import boto3
from opensearchpy import RequestsHttpConnection, AWSV4SignerAuth
from dotenv import load_dotenv

load_dotenv()

# logging.getLogger("mem0.graphs.neptune.neptunedb").setLevel(logging.DEBUG)
# logging.getLogger("mem0.graphs.neptune.base").setLevel(logging.DEBUG)
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
            "collection_name": "mem0ai_neptune_vector_store",
            "endpoint": f"neptune-db://{neptune_host}",
        },
    },
}

m = Memory.from_config(config_dict=config)

app_id = "movies"
user_id = "alice"
category = "movie_night"

m.delete_all(user_id=user_id)

#### ADD "My favourite movie is StarWars: The Empire Strikes Back. Can you remind me to watch this tonight?"
print("My favourite movie is StarWars: The Empire Strikes Back. Can you remind me to watch this tonight?")

messages = [
    {
        "role": "user",
        "content": "My favourite movie is StarWars: The Empire Strikes Back. Can you remind me to watch this tonight?",
    },
]

# Store inferred memories (default behavior)
result = m.add(messages, user_id=user_id, metadata={"category": category})

print("all results:")
all_results = m.get_all(user_id=user_id)
for n in all_results["results"]:
    print(f"node \"{n['memory']}\": [hash: {n['hash']}]")

for e in all_results["relations"]:
    print(f"edge \"{e['source']}\" --{e['relationship']}--> \"{e['target']}\"")

#### ADD "Sure! I've added a reminder to watch Star Wars: Episode V – The Empire Strikes Back at 6:00pm"
print("Sure! I've added a reminder to watch Star Wars: Episode V – The Empire Strikes Back at 6:00pm")
#### ADD "I'd recommend watching the entire trilogy of Star Wars.  Would you like a reminder to watch the remainder of the trilogy?"
print("I'd recommend watching the entire trilogy of Star Wars.  Would you like a reminder to watch the remainder of the trilogy?")

messages = [
    {
        "role": "assistant",
        "content": "Sure! I've added a reminder to watch Star Wars: Episode V – The Empire Strikes Back at 6:00pm",
    },
    {
        "role": "assistant",
        "content": "I'd recommend watching the entire trilogy of Star Wars.  Would you like a reminder to watch the remainder of the trilogy?",
    },
]

# Store inferred memories (default behavior)
result = m.add(messages, user_id=user_id, metadata={"category": category})

# ADD: "What a wonderful suggestion.  I'd love to watch the entire trilogy.  Can you schedule a movie marathon instead?"
print("What a wonderful suggestion.  I'd love to watch the entire trilogy.  Can you schedule a movie marathon instead?")

messages = [
    {
        "role": "user",
        "content": "What a wonderful suggestion.  I'd love to watch the entire trilogy.  Can you schedule a movie marathon instead?",
    },
]

# Store inferred memories (default behavior)
result = m.add(messages, user_id=user_id, metadata={"category": category})

print("all results:")
all_results = m.get_all(user_id=user_id)
for n in all_results["results"]:
    print(f"node \"{n['memory']}\": [hash: {n['hash']}]")

for e in all_results["relations"]:
    print(f"edge \"{e['source']}\" --{e['relationship']}--> \"{e['target']}\"")

# ADD: "I've updated the reminder to watch Star Wars: Episode VI – A New Hope at 6:00pm"
print("I've updated the reminder to watch Star Wars: Episode VI – A New Hope at 6:00pm")
# ADD: "I've added a reminder to watch Star Wars: Episode V – The Empire Strikes Back at 8:00pm"
print("I've added a reminder to watch Star Wars: Episode V – The Empire Strikes Back at 8:00pm")
# ADD: "I've added a reminder to watch Star Wars: Episode VI – Return of the Jedi at midnight"
print("I've added a reminder to watch Star Wars: Episode VI – Return of the Jedi at midnight")
# ADD: "Shall I order a movie appropriate dinner and snacks?"
print("Shall I order a movie appropriate dinner and snacks?")

messages = [
    {
        "role": "assistant",
        "content": "I've updated the reminder to watch Star Wars: Episode VI – A New Hope at 6:00pm",
    },
    {
        "role": "assistant",
        "content": "I've added a reminder to watch Star Wars: Episode V – The Empire Strikes Back at 8:00pm",
    },
    {
        "role": "assistant",
        "content": "I've added a reminder to watch Star Wars: Episode VI – Return of the Jedi at midnight",
    },
    {
        "role": "assistant",
        "content": "Shall I order a movie appropriate dinner and snacks?",
    },
]

result = m.add(messages, user_id=user_id, metadata={"category": category})

print("all results:")
all_results = m.get_all(user_id=user_id)
for n in all_results["results"]:
    print(f"node \"{n['memory']}\": [hash: {n['hash']}]")

for e in all_results["relations"]:
    print(f"edge \"{e['source']}\" --{e['relationship']}--> \"{e['target']}\"")

# ADD: "That's a great idea.  My favourite snacks when watching Star Wars are Wookie Cookies and Yoda Soda."
print("That's a great idea.  My favourite snacks when watching Star Wars are Wookie Cookies and Yoda Soda.")

messages = [
    {
        "role": "user",
        "content": "That's a great idea.  My favourite snacks when watching Star Wars are Wookie Cookies and Yoda Soda.",
    },
]

# Store inferred memories (default behavior)
result = m.add(messages, user_id=user_id, metadata={"category": category})

print("all results:")
all_results = m.get_all(user_id=user_id)
for n in all_results["results"]:
    print(f"node \"{n['memory']}\": [hash: {n['hash']}]")

for e in all_results["relations"]:
    print(f"edge \"{e['source']}\" --{e['relationship']}--> \"{e['target']}\"")

# SEARCH

query = "What's Alice's schedule for tonight?"
search_results = m.search(query, user_id=user_id)
print(query)
for result in search_results["results"]:
    print(f"\"{result['memory']}\" [score: {result['score']}]")
for relation in search_results["relations"]:
    print(f"{relation}")

query = "What's for dinner tonight?"
print(query)
search_results = m.search(query, user_id=user_id)
for result in search_results["results"]:
    print(f"\"{result['memory']}\" [score: {result['score']}]")
for relation in search_results["relations"]:
    print(f"{relation}")

# TEARDOWN

m.delete_all(user_id)
m.reset()