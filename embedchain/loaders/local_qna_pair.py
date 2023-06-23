class LocalQnaPairLoader:

    def load_data(self, content):
        question, answer = content
        content = f"Q: {question}\nA: {answer}"
        meta_data = {
            "url": "local",
        }
        return [{
            "content": content,
            "meta_data": meta_data,
        }]
