from elasticsearch import Elasticsearch
import dotenv
import os

dotenv.load_dotenv()

# Initialize Elasticsearch client with the same configuration
client = Elasticsearch(
    hosts=[f"{os.getenv('ES_URL')}" if os.getenv('ES_PORT') is None else f"{os.getenv('ES_URL')}:{os.getenv('ES_PORT')}"],
    basic_auth=(os.getenv('ES_USERNAME') or "", os.getenv('ES_PASSWORD') or ""),
    verify_certs=True,
)

# Delete the index
if client.indices.exists(index="memories"):
    client.indices.delete(index="memories")
    print("Successfully deleted 'memories' index")
else:
    print("'memories' index does not exist") 