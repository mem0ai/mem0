from langchain.document_loaders import UnstructuredWordDocumentLoader


class DocFileLoader:
    def load_data(self, url):
        loader = UnstructuredWordDocumentLoader(url)
        output = []
        data = loader.load()
        content = data[0].page_content
        meta_data = data[0].metadata
        meta_data["url"] = "local"
        output.append({"content": content, "meta_data": meta_data})
        return output
