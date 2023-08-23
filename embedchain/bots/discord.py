import argparse
import logging
import os
from typing import Any

from .base import BaseBot
import discord
from discord.ext import commands
from dotenv import load_dotenv
load_dotenv()

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="/ec ", intents=intents)

class DiscordBot(BaseBot):
    def __init__(self):
        super().__init__()

    @bot.command()
    async def query_command(self, ctx, *, question: str):
        print(f"User: {ctx.author.name}, Query: {question}")
        try:
            response = self.ask_bot(question)
            await DiscordBot.send_response(ctx, response)
        except Exception as e:
            await DiscordBot.send_response(ctx, "An error occurred. Please try again!")
            print("Error occurred during 'query' command:", e)

    @bot.command()
    async def add_command(self, ctx, *, add: Any):
        print(f"User: {ctx.author.name}, Add: {add}")
        try:
            response = self.add_data(add)
            await DiscordBot.send_response(ctx, response)
        except Exception as e:
            await DiscordBot.send_response(ctx, "An error occurred. Please try again!")
            print("Error occurred during 'add' command:", e)


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

    def start(self, debug=True):
        bot.run(os.environ["DISCORD_BOT_TOKEN"])

    @bot.event
    async def on_ready():
        print(f"Logged in as {bot.user.name}")


    @bot.event
    async def on_command_error(ctx, error):
        if isinstance(error, commands.CommandNotFound):
            await DiscordBot.send_response(ctx, "Invalid command. Please refer to the documentation for correct syntax.")
        else:
            print("Error occurred during command execution:", error)

    @staticmethod
    async def send_response(ctx, message):
        if ctx.guild is None:
            await ctx.send(message)
        else:
            await ctx.reply(message)


def start_command():
    parser = argparse.ArgumentParser(description="EmbedChain WhatsAppBot command line interface")
    parser.add_argument("--host", default="0.0.0.0", help="Host IP to bind")
    parser.add_argument("--port", default=5000, type=int, help="Port to bind")
    args = parser.parse_args()

    discord_bot = DiscordBot()
    discord_bot.start()


if __name__ == "__main__":
    start_command()
