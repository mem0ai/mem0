import concurrent.futures
import hashlib
import logging
from typing import Any, Dict, Optional

import requests

from embedchain.loaders.base_loader import BaseLoader
from embedchain.utils import clean_string


class DiscourseLoader(BaseLoader):
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__()
        if not config:
            raise ValueError(
                "DiscourseLoader requires a config. Check the documentation for the correct format - `https://docs.embedchain.ai/data-sources/discourse`"  # noqa: E501
            )

        self.domain = config.get("domain")
        if not self.domain:
            raise ValueError(
                "DiscourseLoader requires a domain. Check the documentation for the correct format - `https://docs.embedchain.ai/data-sources/discourse`"  # noqa: E501
            )

    def _check_query(self, query):
        if not query or not isinstance(query, str):
            raise ValueError(
                "DiscourseLoader requires a query. Check the documentation for the correct format - `https://docs.embedchain.ai/data-sources/discourse`"  # noqa: E501
            )

    def _load_post(self, post_id):
        post_url = f"{self.domain}/posts/{post_id}.json"
        response = requests.get(post_url)
        response.raise_for_status()
        response_data = response.json()
        post_contents = clean_string(response_data.get("raw"))
        meta_data = {
            "url": post_url,
            "created_at": response_data.get("created_at", ""),
            "username": response_data.get("username", ""),
            "topic_slug": response_data.get("topic_slug", ""),
            "score": response_data.get("score", ""),
        }
        data = {
            "content": post_contents,
            "meta_data": meta_data,
        }
        return data

    def load_data(self, query):
        self._check_query(query)
        data = []
        data_contents = []
        logging.info(f"Searching data on discourse url: {self.domain}, for query: {query}")
        search_url = f"{self.domain}/search.json?q={query}"
        response = requests.get(search_url)
        response.raise_for_status()
        response_data = response.json()
        post_ids = response_data.get("grouped_search_result").get("post_ids")
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future_to_post_id = {executor.submit(self._load_post, post_id): post_id for post_id in post_ids}
            for future in concurrent.futures.as_completed(future_to_post_id):
                post_id = future_to_post_id[future]
                try:
                    post_data = future.result()
                    data.append(post_data)
                except Exception as e:
                    logging.error(f"Failed to load post {post_id}: {e}")
        doc_id = hashlib.sha256((query + ", ".join(data_contents)).encode()).hexdigest()
        response_data = {"doc_id": doc_id, "data": data}
        return response_data
