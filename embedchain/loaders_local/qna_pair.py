from embedchain.utils import markdown_to_plaintext


class QnaPairLoader:

    def load_data(self, content):
        question, answer = content
        answer = markdown_to_plaintext(answer)
        content = f"Q: {question}\nA: {answer}"
        meta_data = {
            "url": "local",
        }
        return [{
            "content": content,
            "meta_data": meta_data,
        }]