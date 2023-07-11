from langchain.document_loaders import PyPDFLoader

from embedchain.utils import clean_string


class PdfFileLoader:
    def load_data(self, url):
        """Load data from a PDF file."""
        loader = PyPDFLoader(url)
        output = []
        pages = loader.load_and_split()
        if not len(pages):
            raise ValueError("No data found")
        for page in pages:
            content = page.page_content
            content = clean_string(content)
            meta_data = page.metadata
            meta_data["url"] = url
            output.append(
                {
                    "content": content,
                    "meta_data": meta_data,
                }
            )
        return output
