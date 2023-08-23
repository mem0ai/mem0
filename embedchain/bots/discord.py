import argparse
import logging
import os

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

from .base import BaseBot

load_dotenv()


intents = discord.Intents.default()
intents.message_content = True

intents = discord.Intents.default()
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)


class DiscordBot(BaseBot):
    def __init__(self):
        super().__init__()

    @tree.command(name="question", description="ask embedchain")
    async def query_command(self, interaction: discord.Interaction, question: str):
        await interaction.response.defer()
        member = client.guilds[0].get_member(client.user.id)
        print(f"User: {member}, Query: {question}")
        try:
            response = self.ask_bot(question)
            await interaction.response.send(response)
        except Exception as e:
            await interaction.response.send("An error occurred. Please try again!")
            print("Error occurred during 'query' command:", e)

    @tree.command(name="add", description="add new content to the embedchain database")
    async def add_command(self, interaction: discord.Interaction, url_or_text: str):
        await interaction.response.defer()
        member = client.guilds[0].get_member(client.user.id)
        print(f"User: {member}, Add: {url_or_text}")
        try:
            response = self.add_data(url_or_text)
            await interaction.response.send(response)
        except Exception as e:
            await interaction.response.send("An error occurred. Please try again!")
            print("Error occurred during 'add' command:", e)

    @tree.command(name="ping", description="Simple ping pong command", guild=discord.Object(id=895731234355937282))
    async def ping(self, interaction: discord.Interaction):
        await interaction.response.send_message("Pong", ephemeral=True)

    def add_data(self, message):
        data = message.split(" ")[-1]
        try:
            self.add(data)
            response = f"Added data from: {data}"
        except Exception:
            logging.exception(f"Failed to add data {data}.")
            response = "Some error occurred while adding data."
        return response

    def ask_bot(self, message):
        try:
            response = self.query(message)
        except Exception:
            logging.exception(f"Failed to query {message}.")
            response = "An error occurred. Please try again!"
        return response

    @client.event
    async def on_ready():
        await tree.sync()
        print("Command tree synced")
        print(f"Logged in as {client.user.name}")

    @tree.error
    async def on_app_command_error(
        interaction: discord.Interaction, error: discord.app_commands.AppCommandError
    ) -> None:
        if isinstance(error, commands.CommandNotFound):
            await interaction.response.send("Invalid command. Please refer to the documentation for correct syntax.")
        else:
            print("Error occurred during command execution:", error)

    def start(self, debug=True):
        client.run(os.environ["DISCORD_BOT_TOKEN"])


def start_command():
    parser = argparse.ArgumentParser(description="EmbedChain WhatsAppBot command line interface")
    parser.add_argument("--host", default="0.0.0.0", help="Host IP to bind")
    parser.add_argument("--port", default=5000, type=int, help="Port to bind")
    args = parser.parse_args()

    discord_bot = DiscordBot()
    discord_bot.start()


if __name__ == "__main__":
    start_command()
