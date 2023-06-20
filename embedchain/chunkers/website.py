import hashlib

from langchain.text_splitter import RecursiveCharacterTextSplitter


TEXT_SPLITTER_CHUNK_PARAMS = {
    "chunk_size": 500,
    "chunk_overlap": 0,
    "length_function": len,
}

TEXT_SPLITTER = RecursiveCharacterTextSplitter(**TEXT_SPLITTER_CHUNK_PARAMS)


class WebsiteChunker:

    def create_chunks(self, loader, url):
        documents = []
        ids = []
        datas = loader.load_data(url)
        metadatas = []
        for data in datas:
            content = data["content"]
            meta_data = data["meta_data"]
            chunks = TEXT_SPLITTER.split_text(content)
            url = meta_data["url"]
            for chunk in chunks:
                chunk_id = hashlib.sha256((chunk + url).encode()).hexdigest()
                ids.append(chunk_id)
                documents.append(chunk)
                metadatas.append(meta_data)
        return {
            "documents": documents,
            "ids": ids,
            "metadatas": metadatas,
        }