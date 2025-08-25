from mem0 import Memory
import os
import logging
import sys
import boto3
from opensearchpy import RequestsHttpConnection, AWSV4SignerAuth
from dotenv import load_dotenv

load_dotenv()

logging.getLogger("mem0.graphs.neptune.neptunegraph").setLevel(logging.DEBUG)
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

# embedding_model_dims = 1536

neptune_host = os.environ.get("GRAPH_HOST")
neptune_graph_identifier = os.environ.get("GRAPH_ID")

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
        "provider": "neptune",
        "config": {
            "endpoint": f"neptune-graph://{neptune_graph_identifier}",
        },
    },
}

m = Memory.from_config(config_dict=config)

app_id = "movies"
user_id = "alice"

m.delete_all(user_id=user_id)

messages = [
    {
        "role": "user",
        "content": "I'm planning to watch a movie tonight. Any recommendations?",
    },
]

# Store inferred memories (default behavior)
result = m.add(messages, user_id=user_id, metadata={"category": "movie_recommendations"})

all_results = m.get_all(user_id=user_id)
for n in all_results["results"]:
    print(f"node \"{n['memory']}\": [hash: {n['hash']}]")

for e in all_results["relations"]:
    print(f"edge \"{e['source']}\" --{e['relationship']}--> \"{e['target']}\"")