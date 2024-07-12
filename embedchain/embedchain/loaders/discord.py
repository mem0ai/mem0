import hashlib
import logging
import os

from embedchain.helpers.json_serializable import register_deserializable
from embedchain.loaders.base_loader import BaseLoader

logger = logging.getLogger(__name__)


@register_deserializable
class DiscordLoader(BaseLoader):
    """
    Load data from a Discord Channel ID.
    """

    def __init__(self):
        if not os.environ.get("DISCORD_TOKEN"):
            raise ValueError("DISCORD_TOKEN is not set")

        self.token = os.environ.get("DISCORD_TOKEN")

    @staticmethod
    def _format_message(message):
        return {
            "message_id": message.id,
            "content": message.content,
            "author": {
                "id": message.author.id,
                "name": message.author.name,
                "discriminator": message.author.discriminator,
            },
            "created_at": message.created_at.isoformat(),
            "attachments": [
                {
                    "id": attachment.id,
                    "filename": attachment.filename,
                    "size": attachment.size,
                    "url": attachment.url,
                    "proxy_url": attachment.proxy_url,
                    "height": attachment.height,
                    "width": attachment.width,
                }
                for attachment in message.attachments
            ],
            "embeds": [
                {
                    "title": embed.title,
                    "type": embed.type,
                    "description": embed.description,
                    "url": embed.url,
                    "timestamp": embed.timestamp.isoformat(),
                    "color": embed.color,
                    "footer": {
                        "text": embed.footer.text,
                        "icon_url": embed.footer.icon_url,
                        "proxy_icon_url": embed.footer.proxy_icon_url,
                    },
                    "image": {
                        "url": embed.image.url,
                        "proxy_url": embed.image.proxy_url,
                        "height": embed.image.height,
                        "width": embed.image.width,
                    },
                    "thumbnail": {
                        "url": embed.thumbnail.url,
                        "proxy_url": embed.thumbnail.proxy_url,
                        "height": embed.thumbnail.height,
                        "width": embed.thumbnail.width,
                    },
                    "video": {
                        "url": embed.video.url,
                        "height": embed.video.height,
                        "width": embed.video.width,
                    },
                    "provider": {
                        "name": embed.provider.name,
                        "url": embed.provider.url,
                    },
                    "author": {
                        "name": embed.author.name,
                        "url": embed.author.url,
                        "icon_url": embed.author.icon_url,
                        "proxy_icon_url": embed.author.proxy_icon_url,
                    },
                    "fields": [
                        {
                            "name": field.name,
                            "value": field.value,
                            "inline": field.inline,
                        }
                        for field in embed.fields
                    ],
                }
                for embed in message.embeds
            ],
        }

    def load_data(self, channel_id: str):
        """Load data from a Discord Channel ID."""
        import discord

        messages = []

        class DiscordClient(discord.Client):
            async def on_ready(self) -> None:
                logger.info("Logged on as {0}!".format(self.user))
                try:
                    channel = self.get_channel(int(channel_id))
                    if not isinstance(channel, discord.TextChannel):
                        raise ValueError(
                            f"Channel {channel_id} is not a text channel. " "Only text channels are supported for now."
                        )
                    threads = {}

                    for thread in channel.threads:
                        threads[thread.id] = thread

                    async for message in channel.history(limit=None):
                        messages.append(DiscordLoader._format_message(message))
                        if message.id in threads:
                            async for thread_message in threads[message.id].history(limit=None):
                                messages.append(DiscordLoader._format_message(thread_message))

                except Exception as e:
                    logger.error(e)
                    await self.close()
                finally:
                    await self.close()

        intents = discord.Intents.default()
        intents.message_content = True
        client = DiscordClient(intents=intents)
        client.run(self.token)

        metadata = {
            "url": channel_id,
        }

        messages = str(messages)

        doc_id = hashlib.sha256((messages + channel_id).encode()).hexdigest()

        return {
            "doc_id": doc_id,
            "data": [
                {
                    "content": messages,
                    "meta_data": metadata,
                }
            ],
        }
