import hashlib


class BaseChunker:
    def __init__(self, text_splitter):
        self.text_splitter = text_splitter

    def create_chunks(self, loader, src):
        """
        Loads data and chunks it.

        :param loader: The loader which's `load_data` method is used to create the raw data.
        :param src: The data to be handled by the loader. Can be a URL for remote sources or local content for local loaders. 
        """
        documents = []
        ids = []
        idMap = {}
        datas = loader.load_data(src)
        metadatas = []
        for data in datas:
            content = data["content"]
            meta_data = data["meta_data"]
            url = meta_data["url"]

            chunks = self.text_splitter.split_text(content)

            for chunk in chunks:
                chunk_id = hashlib.sha256((chunk + url).encode()).hexdigest()
                if (idMap.get(chunk_id) is None):
                    idMap[chunk_id] = True
                    ids.append(chunk_id)
                    documents.append(chunk)
                    metadatas.append(meta_data)
        return {
            "documents": documents,
            "ids": ids,
            "metadatas": metadatas,
        }
