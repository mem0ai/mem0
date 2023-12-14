import chainlit as cl
from embedchain.llm.openai import OpenAILlm
from embedchain.config import BaseLlmConfig

import os

os.environ["OPENAI_API_KEY"] = "sk-xxx"


@cl.on_chat_start
async def on_chat_start():
    config = BaseLlmConfig(stream=True)
    llm = OpenAILlm(config)
    cl.user_session.set("llm", llm)


@cl.on_message
async def on_message(message: cl.Message):
    llm = cl.user_session.get("llm")
    response_message = llm.get_llm_model_answer(message.content)
    await cl.Message(content=response_message).send()
