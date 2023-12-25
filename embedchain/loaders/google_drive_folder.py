import hashlib
import re

from langchain.document_loaders import UnstructuredFileIOLoader, GoogleDriveLoader

from embedchain.helpers.json_serializable import register_deserializable
from embedchain.loaders.base_loader import BaseLoader


@register_deserializable
class GoogleDriveFolderLoader(BaseLoader):
    @staticmethod
    def _get_drive_id_from_url(url: str):
        regex = r"^https:\/\/drive\.google\.com\/drive\/(?:u\/\d+\/)folders\/([a-zA-Z0-9_-]+)$"
        if re.match(regex, url):
            return url.split("/")[-1]
        raise ValueError(
            f"The url provided does {url} not match a google drive folder url. Example drive url: https://drive.google.com/drive/u/0/folders/xxxx"
            # noqa: E501
        )

    def load_data(self, url: str):
        """Load data from a Google drive folder."""
        folder_id: str = self._get_drive_id_from_url(url)
        loader = GoogleDriveLoader(
            folder_id=folder_id,
            recursive=True,
            file_loader_cls=UnstructuredFileIOLoader,
            file_loader_kwargs={"mode": "elements"},
        )

        docs = loader.load()

        data = []
        all_content = []
        for doc in docs:
            all_content.append(doc.page_content)
            # renames source to url for later use.
            doc.metadata["url"] = doc.metadata.pop("source")
            data.append({"content": doc.page_content, "meta_data": doc.metadata})

        doc_id = hashlib.sha256((" ".join(all_content) + url).encode()).hexdigest()
        return {"doc_id": doc_id, "data": data}
