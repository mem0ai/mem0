import os

try:
    from llama_hub.gmail.base import GmailReader
except ImportError:
    raise ImportError("Notion requires extra dependencies. Install with `pip install embedchain[community]`") from None

from embedchain.loaders.base_loader import BaseLoader

class GMAILLoader(BaseLoader):
    @staticmethod
    def load_data(query):
        if not os.path.isfile("token.json"):
            raise FileNotFoundError(f"You must download the valid credentials file from your google \
                dev account. Refer this `https://cloud.google.com/docs/authentication/api-keys`")
        
        loader = GmailReader(query=query)
        data = loader.load_data()
        print("GMAIL DATA: ", data, query)
        return {
            "doc_id": "",
            "data": []
        }