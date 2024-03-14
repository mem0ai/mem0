import hashlib
import logging
import os
import ssl
from typing import Any, Optional

import certifi

from embedchain.loaders.base_loader import BaseLoader
from embedchain.utils.misc import clean_string

SLACK_API_BASE_URL = "https://www.slack.com/api/"

logger = logging.getLogger(__name__)


class SlackLoader(BaseLoader):
    def __init__(self, config: Optional[dict[str, Any]] = None):
        super().__init__()

        self.config = config if config else {}

        if "base_url" not in self.config:
            self.config["base_url"] = SLACK_API_BASE_URL

        self.client = None
        self._setup_loader(self.config)

    def _setup_loader(self, config: dict[str, Any]):
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

        logger.info(f"Creating Slack Loader with config: {config}")
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
        logger.info("Slack Loader setup successful!")

    @staticmethod
    def _check_query(query):
        if not isinstance(query, str):
            raise ValueError(
                f"Invalid query passed to Slack loader, found: {query}. Check `https://docs.embedchain.ai/data-sources/slack` to learn more."  # noqa:E501
            )

    def load_data(self, query):
        self._check_query(query)
        try:
            data = []
            data_content = []

            logger.info(f"Searching slack conversations for query: {query}")
            results = self.client.search_messages(
                query=query,
                sort="timestamp",
                sort_dir="desc",
                count=self.config.get("count", 100),
            )

            messages = results.get("messages")
            num_message = len(messages)
            logger.info(f"Found {num_message} messages for query: {query}")

            matches = messages.get("matches", [])
            for message in matches:
                url = message.get("permalink")
                text = message.get("text")
                content = clean_string(text)

                message_meta_data_keys = ["iid", "team", "ts", "type", "user", "username"]
                metadata = {}
                for key in message.keys():
                    if key in message_meta_data_keys:
                        metadata[key] = message.get(key)
                metadata.update({"url": url})

                data.append(
                    {
                        "content": content,
                        "meta_data": metadata,
                    }
                )
                data_content.append(content)
            doc_id = hashlib.md5((query + ", ".join(data_content)).encode()).hexdigest()
            return {
                "doc_id": doc_id,
                "data": data,
            }
        except Exception as e:
            logger.warning(f"Error in loading slack data: {e}")
            raise ValueError(
                f"Error in loading slack data: {e}. Check `https://docs.embedchain.ai/data-sources/slack` to learn more."  # noqa:E501
            ) from e
