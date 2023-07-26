from embedchain.loaders.base_loader import BaseLoader


class LocalQnaPairLoader(BaseLoader):
    def load_data(self, content):
        """Load data from a local QnA pair."""
        question, answer = content
        content = f"Q: {question}\nA: {answer}"
        meta_data = {
            "url": "local",
        }
        return [
            {
                "content": content,
                "meta_data": meta_data,
            }
        ]
