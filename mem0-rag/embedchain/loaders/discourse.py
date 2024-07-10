import hashlib
import logging
import time
from typing import Any, Optional

import requests

from embedchain.loaders.base_loader import BaseLoader
from embedchain.utils.misc import clean_string

logger = logging.getLogger(__name__)


class DiscourseLoader(BaseLoader):
    def __init__(self, config: Optional[dict[str, Any]] = None):
        super().__init__()
        if not config:
            raise ValueError(
                "DiscourseLoader requires a config. Check the documentation for the correct format - `https://docs.embedchain.ai/components/data-sources/discourse`"  # noqa: E501
            )

        self.domain = config.get("domain")
        if not self.domain:
            raise ValueError(
                "DiscourseLoader requires a domain. Check the documentation for the correct format - `https://docs.embedchain.ai/components/data-sources/discourse`"  # noqa: E501
            )

    def _check_query(self, query):
        if not query or not isinstance(query, str):
            raise ValueError(
                "DiscourseLoader requires a query. Check the documentation for the correct format - `https://docs.embedchain.ai/components/data-sources/discourse`"  # noqa: E501
            )

    def _load_post(self, post_id):
        post_url = f"{self.domain}posts/{post_id}.json"
        response = requests.get(post_url)
        try:
            response.raise_for_status()
        except Exception as e:
            logger.error(f"Failed to load post {post_id}: {e}")
            return
        response_data = response.json()
        post_contents = clean_string(response_data.get("raw"))
        metadata = {
            "url": post_url,
            "created_at": response_data.get("created_at", ""),
            "username": response_data.get("username", ""),
            "topic_slug": response_data.get("topic_slug", ""),
            "score": response_data.get("score", ""),
        }
        data = {
            "content": post_contents,
            "meta_data": metadata,
        }
        return data

    def load_data(self, query):
        self._check_query(query)
        data = []
        data_contents = []
        logger.info(f"Searching data on discourse url: {self.domain}, for query: {query}")
        search_url = f"{self.domain}search.json?q={query}"
        response = requests.get(search_url)
        try:
            response.raise_for_status()
        except Exception as e:
            raise ValueError(f"Failed to search query {query}: {e}")
        response_data = response.json()
        post_ids = response_data.get("grouped_search_result").get("post_ids")
        for id in post_ids:
            post_data = self._load_post(id)
            if post_data:
                data.append(post_data)
                data_contents.append(post_data.get("content"))
            # Sleep for 0.4 sec, to avoid rate limiting. Check `https://meta.discourse.org/t/api-rate-limits/208405/6`
            time.sleep(0.4)
        doc_id = hashlib.sha256((query + ", ".join(data_contents)).encode()).hexdigest()
        response_data = {"doc_id": doc_id, "data": data}
        return response_data
