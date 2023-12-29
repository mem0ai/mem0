import os

import chainlit as cl

from embedchain import App

os.environ["OPENAI_API_KEY"] = "sk-xxx"


@cl.on_chat_start
async def on_chat_start():
    app = App.from_config(
        config={
            "app": {"config": {"name": "chainlit-app"}},
            "llm": {
                "config": {
                    "stream": True,
                }
            },
        }
    )
    # import your data here
    app.add("https://www.forbes.com/profile/elon-musk/")
    app.collect_metrics = False
    cl.user_session.set("app", app)


@cl.on_message
async def on_message(message: cl.Message):
    app = cl.user_session.get("app")
    msg = cl.Message(content="")
    for chunk in await cl.make_async(app.chat)(message.content):
        await msg.stream_token(chunk)

    await msg.send()
