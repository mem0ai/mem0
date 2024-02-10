import base64
import hashlib
import os
from pathlib import Path

from openai import OpenAI

from embedchain.helpers.json_serializable import register_deserializable
from embedchain.loaders.base_loader import BaseLoader

DESCRIBE_IMAGE_PROMPT = "Describe the image:"


@register_deserializable
class ImageLoader(BaseLoader):
    def __init__(self, max_tokens: int = 500, api_key: str = None, prompt: str = None):
        super().__init__()
        self.custom_prompt = prompt or DESCRIBE_IMAGE_PROMPT
        self.max_tokens = max_tokens
        self.api_key = api_key or os.environ["OPENAI_API_KEY"]
        self.client = OpenAI(api_key=self.api_key)

    @staticmethod
    def _encode_image(image_path: str):
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode("utf-8")

    def _create_completion_request(self, content: str):
        return self.client.chat.completions.create(
            model="gpt-4-vision-preview", messages=[{"role": "user", "content": content}], max_tokens=self.max_tokens
        )

    def _process_url(self, url: str):
        if url.startswith("http"):
            return [{"type": "text", "text": self.custom_prompt}, {"type": "image_url", "image_url": {"url": url}}]
        elif Path(url).is_file():
            extension = Path(url).suffix.lstrip(".")
            encoded_image = self._encode_image(url)
            image_data = f"data:image/{extension};base64,{encoded_image}"
            return [{"type": "text", "text": self.custom_prompt}, {"type": "image", "image_url": {"url": image_data}}]
        else:
            raise ValueError(f"Invalid URL or file path: {url}")

    def load_data(self, url: str):
        content = self._process_url(url)
        response = self._create_completion_request(content)
        content = response.choices[0].message.content

        doc_id = hashlib.sha256((content + url).encode()).hexdigest()
        return {"doc_id": doc_id, "data": [{"content": content, "meta_data": {"url": url, "type": "image"}}]}
