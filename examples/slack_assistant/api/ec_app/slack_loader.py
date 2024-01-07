import hashlib
import logging
import os
import ssl
from typing import Any, Dict, Optional
from urllib.parse import parse_qs, urlparse

import certifi

from embedchain.loaders.base_loader import BaseLoader
from embedchain.utils.misc import clean_string


def get_thread_ts(url, parent_ts):
    parsed_url = urlparse(url)
    query_params = parse_qs(parsed_url.query)
    thread_ts = query_params.get("thread_ts", [None])[0]
    return thread_ts if thread_ts else parent_ts


SLACK_API_BASE_URL = "https://www.slack.com/api/"


class SlackLoader(BaseLoader):
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__()

        self.config = config if config else {}

        if "base_url" not in self.config:
            self.config["base_url"] = SLACK_API_BASE_URL

        self.client = None
        self._setup_loader(self.config)

    def _setup_loader(self, config: Dict[str, Any]):
        try:
            from slack_sdk import WebClient
        except ImportError as e:
            raise ImportError(
                "Slack loader requires extra dependencies. \
                Install with `pip install --upgrade embedchain[slack]`"
            ) from e

        if os.getenv("SLACK_USER_TOKEN") is None:
            raise ValueError(
                "SLACK_USER_TOKEN environment variables not provided. Check `https://docs.embedchain.ai/data-sources/slack` to learn more."  # noqa:E501
            )

        logging.info(f"Creating Slack Loader with config: {config}")
        # get slack client config params
        slack_bot_token = os.getenv("SLACK_USER_TOKEN")
        ssl_cert = ssl.create_default_context(cafile=certifi.where())
        base_url = config.get("base_url", SLACK_API_BASE_URL)
        headers = config.get("headers")
        # for Org-Wide App
        team_id = config.get("team_id")

        self.client = WebClient(
            token=slack_bot_token,
            base_url=base_url,
            ssl=ssl_cert,
            headers=headers,
            team_id=team_id,
        )
        logging.info("Slack Loader setup successful!")

    def _check_query(self, query):
        if not isinstance(query, str):
            raise ValueError(
                f"Invalid query passed to Slack loader, found: {query}. Check `https://docs.embedchain.ai/data-sources/slack` to learn more."  # noqa:E501
            )

    def load_data(self, query):
        self._check_query(query)
        try:
            message_data = []
            data = []
            data_content = []

            logging.info(f"Searching slack conversations for {query=}")
            results = self.client.search_messages(
                query=query,
                sort="timestamp",
                sort_dir="desc",
                count=self.config.get("count", 100),
            )
            messages = results.get("messages")
            num_message = messages.get("total")
            total_pages = messages.get("pagination").get("page_count")
            current_page = messages.get("pagination").get("page")
            print(f"Collecting {num_message} messages for {query=}, from {total_pages=}")
            message_data.extend(messages.get("matches", []))
            for page in range(current_page + 1, total_pages + 1):
                results = self.client.search_messages(
                    query=query, sort="timestamp", sort_dir="desc", count=self.config.get("count", 100), page=page
                )
                messages = results.get("messages")
                message_data.extend(messages.get("matches", []))

            # group thread messages
            print("Grouping messages in threads...")
            message_threads = {}
            for message in message_data:
                url = message.get("permalink")
                text = message.get("text")
                content = clean_string(text)

                message_meta_data_keys = ["iid", "team", "ts", "type", "user", "username"]
                meta_data = {}
                for key in message.keys():
                    if key in message_meta_data_keys:
                        meta_data[key] = message.get(key)
                meta_data.update({"url": url})
                thread_ts = get_thread_ts(url, meta_data.get("ts"))
                if thread_ts not in message_threads:
                    message_threads[thread_ts] = [(content, meta_data, meta_data.get("ts"))]
                else:
                    message_threads[thread_ts].append((content, meta_data, meta_data.get("ts")))

            for url, messages in message_threads.items():
                messages = sorted(messages, key=lambda x: x[2])
                content = "\n".join([f"@{message[1].get('username')}: {message[0]}" for message in messages])
                meta_data = messages[0][1]
                data.append(
                    {
                        "content": content,
                        "meta_data": meta_data,
                    }
                )
                data_content.append(content)

            doc_id = hashlib.md5((query + ", ".join(data_content)).encode()).hexdigest()
            return {
                "doc_id": doc_id,
                "data": data,
            }
        except Exception as e:
            logging.warning(f"Error in loading slack data: {e}")
            raise ValueError(
                f"Error in loading slack data: {e}. Check `https://docs.embedchain.ai/components/data-sources/slack` to learn more."  # noqa:E501
            ) from e
