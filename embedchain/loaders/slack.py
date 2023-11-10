import hashlib
import json
import logging
import os
import ssl
from typing import Any, Dict, Optional

import certifi

from embedchain.loaders.base_loader import BaseLoader
from embedchain.utils import clean_string

SLACK_API_BASE_URL = "https://www.slack.com/api/"


class SlackLoader(BaseLoader):
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__()

        if config is not None:
            self.config = config
        else:
            self.config = {"base_url": SLACK_API_BASE_URL}

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

        if os.getenv("SLACK_BOT_TOKEN") is None:
            raise ValueError(
                "SLACK_BOT_TOKEN environment variables not provided. Check `https://docs.embedchain.ai/data-sources/slack` to learn more."  # noqa:E501
            )

        logging.info(f"Creating Slack Loader with config: {config}")
        # get slack client config params
        slack_bot_token = os.getenv("SLACK_BOT_TOKEN")
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
        # get the user info and team info
        response = self.client.auth_test()
        self.client_team_id = response.get("team_id")

        # show the list of channels that can be accessed by the bot
        response = self.client.conversations_list()
        channels = response.get("channels")
        channel_names = [channel.get("name") for channel in channels]
        logging.info(f"Slack Loader has access to the following channels: {channel_names}")
        self.channel_names_with_id = {channel.get("name"): channel.get("id") for channel in channels}

    def _is_valid_json(self, query):
        try:
            json.loads(query)
            return True
        except ValueError:
            logging.warning(f"Pass the valid json query in slack loader, found: {query}")
            return False

    def _check_query(self, query):
        if not isinstance(query, str) or not self._is_valid_json(query):
            raise ValueError(
                f"Invalid query passed to Slack loader, found: {query}. Check `https://docs.embedchain.ai/data-sources/slack` to learn more."  # noqa:E501
            )

    def load_data(self, query):
        self._check_query(query)
        try:
            data = []
            data_content = []
            json_query = json.loads(query)
            channels = json_query.keys()
            logging.info(f"Loading slack conversations from channels: {channels}")
            for _, channel_name in enumerate(channels):
                if channel_name not in self.channel_names_with_id:
                    logging.warning(f"Channel with name {channel_name} not found, skipping...")
                    continue
                channel_id = self.channel_names_with_id.get(channel_name)
                channel_config = json_query.get(channel_id, {})
                last_seen_time = channel_config.get("last_seen", 0)
                limit = channel_config.get("limit", 100)
                response = self.client.conversations_history(
                    channel=channel_id,
                    inclusive=True,
                    oldest=last_seen_time,
                    limit=min(limit, 1000),
                )
                # Check https://api.slack.com/methods/conversations.history for example response
                messages = response.get("messages")
                content = clean_string(json.dumps(messages))
                data.append(
                    {
                        "content": content,
                        "meta_data": {"url": f"https://app.slack.com/client/{self.client_team_id}/{channel_id}"},
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
                f"Error in loading slack data: {e}. Check `https://docs.embedchain.ai/data-sources/slack` to learn more."  # noqa:E501
            ) from e

    def create_query(self, from_dict: Dict[str, Any]):
        query_channels = from_dict.keys()
        for query_channel in query_channels:
            if query_channel not in self.channel_names_with_id:
                raise ValueError(
                    f"Invalid channel name: {query_channel} while creating slack query. Channel name must be from {self.channel_names_with_id.keys()}"  # noqa:E501
                )
        return json.dumps(from_dict)
