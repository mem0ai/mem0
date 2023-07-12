from string import Template

from dotenv import load_dotenv

from embedchain import App
from embedchain.config import AddConfig, InitConfig, QueryConfig

load_dotenv()

config = InitConfig(log_level="INFO")

app = App(config=config)
# app.reset()
# app = App(config=config)

chunkerconfig = {
    "chunker": {
        "chunk_size": 1,
        "chunk_overlap": 1,
        "length_function": len,
    }
}
config = AddConfig(chunkerconfig)
app.add(
    "text",
    "I apologize for the confusion. Since the RecursiveCharacterTextSplitter is not used in the provided code, you can remove the import statement for RecursiveCharacterTextSplitter from the test file. The import is unnecessary in this case.",
)

template = """
You are a chatbot. Answer my question, marked as query, given the context provided.
If you find any product name in the query, or get the feeling that the user is searching for a product or item enter search-bot mode.
In search bot-mode you don't give full sentence answers. You just reply with the name of the product, and wrap it in triple curly-brackets and nothing else. This is important.

Context: $context

Query: $query

Helpful answer:
"""

options = QueryConfig(template=Template(template))

r = app.query("Where can I buy Air Max 97?", options)
print(r)
