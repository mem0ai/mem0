import hashlib


class BaseChunker:
    def __init__(self, text_splitter):
        ''' Initialize the chunker. '''
        self.text_splitter = text_splitter

    def create_chunks(self, loader, url):
        ''' Create chunks from a document. '''
        documents = []
        ids = []
        datas = loader.load_data(url)
        metadatas = []
        for data in datas:
            content = data["content"]
            meta_data = data["meta_data"]
            chunks = self.text_splitter.split_text(content)
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
