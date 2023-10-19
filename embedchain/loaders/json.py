import hashlib

from langchain.document_loaders.json_loader import \
    JSONLoader as LangchainJSONLoader

from embedchain.loaders.base_loader import BaseLoader

langchain_json_jq_schema = 'to_entries | map("\(.key): \(.value|tostring)") | .[]'


class JSONLoader(BaseLoader):
    @staticmethod
    def load_data(content):
        """Load a json file. Each data point is a key value pair."""
        data = []
        data_content = []
        loader = LangchainJSONLoader(content, text_content=False, jq_schema=langchain_json_jq_schema)
        docs = loader.load()
        for doc in docs:
            meta_data = doc.metadata
            data.append({"content": doc.page_content, "meta_data": {"url": content, "row": meta_data["seq_num"]}})
            data_content.append(doc.page_content)
        doc_id = hashlib.sha256((content + ", ".join(data_content)).encode()).hexdigest()
        return {"doc_id": doc_id, "data": data}
