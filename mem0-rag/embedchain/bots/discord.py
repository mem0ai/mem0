import argparse
import logging
import os

from embedchain.helpers.json_serializable import register_deserializable

from .base import BaseBot

try:
    import discord
    from discord import app_commands
    from discord.ext import commands
except ModuleNotFoundError:
    raise ModuleNotFoundError(
        "The required dependencies for Discord are not installed." "Please install with `pip install discord==2.3.2`"
    ) from None


logger = logging.getLogger(__name__)

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

# Invite link example
# https://discord.com/api/oauth2/authorize?client_id={DISCORD_CLIENT_ID}&permissions=2048&scope=bot


@register_deserializable
class DiscordBot(BaseBot):
    def __init__(self, *args, **kwargs):
        BaseBot.__init__(self, *args, **kwargs)

    def add_data(self, message):
        data = message.split(" ")[-1]
        try:
            self.add(data)
            response = f"Added data from: {data}"
        except Exception:
            logger.exception(f"Failed to add data {data}.")
            response = "Some error occurred while adding data."
        return response

    def ask_bot(self, message):
        try:
            response = self.query(message)
        except Exception:
            logger.exception(f"Failed to query {message}.")
            response = "An error occurred. Please try again!"
        return response

    def start(self):
        client.run(os.environ["DISCORD_BOT_TOKEN"])


# @tree decorator cannot be used in a class. A global discord_bot is used as a workaround.


@tree.command(name="question", description="ask embedchain")
async def query_command(interaction: discord.Interaction, question: str):
    await interaction.response.defer()
    member = client.guilds[0].get_member(client.user.id)
    logger.info(f"User: {member}, Query: {question}")
    try:
        answer = discord_bot.ask_bot(question)
        if args.include_question:
            response = f"> {question}\n\n{answer}"
        else:
            response = answer
        await interaction.followup.send(response)
    except Exception as e:
        await interaction.followup.send("An error occurred. Please try again!")
        logger.error("Error occurred during 'query' command:", e)


@tree.command(name="add", description="add new content to the embedchain database")
async def add_command(interaction: discord.Interaction, url_or_text: str):
    await interaction.response.defer()
    member = client.guilds[0].get_member(client.user.id)
    logger.info(f"User: {member}, Add: {url_or_text}")
    try:
        response = discord_bot.add_data(url_or_text)
        await interaction.followup.send(response)
    except Exception as e:
        await interaction.followup.send("An error occurred. Please try again!")
        logger.error("Error occurred during 'add' command:", e)


@tree.command(name="ping", description="Simple ping pong command")
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message("Pong", ephemeral=True)


@tree.error
async def on_app_command_error(interaction: discord.Interaction, error: discord.app_commands.AppCommandError) -> None:
    if isinstance(error, commands.CommandNotFound):
        await interaction.followup.send("Invalid command. Please refer to the documentation for correct syntax.")
    else:
        logger.error("Error occurred during command execution:", error)


@client.event
async def on_ready():
    # TODO: Sync in admin command, to not hit rate limits.
    # This might be overkill for most users, and it would require to set a guild or user id, where sync is allowed.
    await tree.sync()
    logger.debug("Command tree synced")
    logger.info(f"Logged in as {client.user.name}")


def start_command():
    parser = argparse.ArgumentParser(description="EmbedChain DiscordBot command line interface")
    parser.add_argument(
        "--include-question",
        help="include question in query reply, otherwise it is hidden behind the slash command.",
        action="store_true",
    )
    global args
    args = parser.parse_args()

    global discord_bot
    discord_bot = DiscordBot()
    discord_bot.start()


if __name__ == "__main__":
    start_command()
