from embedchain.loaders.base_loader import BaseLoader


class LocalTextLoader(BaseLoader):
    def load_data(self, content):
        """Load data from a local text file."""
        meta_data = {
            "url": "local",
        }
        return [
            {
                "content": content,
                "meta_data": meta_data,
            }
        ]
