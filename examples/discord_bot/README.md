# Discord Bot

This is a docker template to create your own Discord bot using the embedchain package. To know more about the bot and how to use it, go [here](https://docs.embedchain.ai/examples/discord_bot).

To run this use the following command,

```bash
docker run --name discord-bot -e OPENAI_API_KEY=sk-xxx -e DISCORD_BOT_TOKEN=xxx -p 8080:8080 embedchain/discord-bot:latest
```
