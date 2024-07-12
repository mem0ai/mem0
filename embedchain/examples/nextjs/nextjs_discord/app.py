import logging
import os

import discord
import dotenv
import requests

dotenv.load_dotenv(".env")

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)
discord_bot_name = os.environ["DISCORD_BOT_NAME"]

logger = logging.getLogger(__name__)


class NextJSBot:
    def __init__(self) -> None:
        logger.info("NextJS Bot powered with embedchain.")

    def add(self, _):
        raise ValueError("Add is not implemented yet")

    def query(self, message, citations: bool = False):
        url = os.environ["EC_APP_URL"] + "/query"
        payload = {
            "question": message,
            "citations": citations,
        }
        try:
            response = requests.request("POST", url, json=payload)
            try:
                response = response.json()
            except Exception:
                logger.error(f"Failed to parse response: {response}")
                response = {}
            return response
        except Exception:
            logger.exception(f"Failed to query {message}.")
            response = "An error occurred. Please try again!"
        return response

    def start(self):
        discord_token = os.environ["DISCORD_BOT_TOKEN"]
        client.run(discord_token)


NEXTJS_BOT = NextJSBot()


@client.event
async def on_ready():
    logger.info(f"User {client.user.name} logged in with id: {client.user.id}!")


def _get_question(message):
    user_ids = message.raw_mentions
    if len(user_ids) > 0:
        for user_id in user_ids:
            # remove mentions from message
            question = message.content.replace(f"<@{user_id}>", "").strip()
    return question


async def answer_query(message):
    if (
        message.channel.type == discord.ChannelType.public_thread
        or message.channel.type == discord.ChannelType.private_thread
    ):
        await message.channel.send(
            "🧵 Currently, we don't support answering questions in threads. Could you please send your message in the channel for a swift response? Appreciate your understanding! 🚀"  # noqa: E501
        )
        return

    question = _get_question(message)
    print("Answering question: ", question)
    thread = await message.create_thread(name=question)
    await thread.send("🎭 Putting on my thinking cap, brb with an epic response!")
    response = NEXTJS_BOT.query(question, citations=True)

    default_answer = "Sorry, I don't know the answer to that question. Please refer to the documentation.\nhttps://nextjs.org/docs"  # noqa: E501
    answer = response.get("answer", default_answer)

    contexts = response.get("contexts", [])
    if contexts:
        sources = list(set(map(lambda x: x[1]["url"], contexts)))
        answer += "\n\n**Sources**:\n"
        for i, source in enumerate(sources):
            answer += f"- {source}\n"

    sent_message = await thread.send(answer)
    await sent_message.add_reaction("😮")
    await sent_message.add_reaction("👍")
    await sent_message.add_reaction("❤️")
    await sent_message.add_reaction("👎")


@client.event
async def on_message(message):
    mentions = message.mentions
    if len(mentions) > 0 and any([user.bot and user.name == discord_bot_name for user in mentions]):
        await answer_query(message)


def start_bot():
    NEXTJS_BOT.start()


if __name__ == "__main__":
    start_bot()
