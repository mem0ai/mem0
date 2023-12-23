from fastapi import Body, FastAPI, responses
from modal import Image, Stub, asgi_app
from embedchain import Pipeline
from functools import lru_cache

@lru_cache(maxsize=1)
def get_embedchain_app():
    """
    This function uses lru_cache to cache the model.
    It will only download the model if it's not already cached.
    """
    return Pipeline.from_config(config={
        "app": {
            "config": {
                "name": "open-source-rag-app"
            }
        },
        "llm": {
            "provider": "gpt4all",
            "config": {
                "model": "mistral-7b-instruct-v0.1.Q4_0.gguf"
            }
        },
        "embedder": {
            "provider": "gpt4all",
        }
    })

image = Image.from_registry("ubuntu:22.04", add_python="3.11").pip_install(
    "embedchain[dataloaders,opensource]",
    "streamlit",
    "fastapi",
    "asgiproxy"
)

stub = Stub(
    name="open-source-rag-app",
    image=image,
)

web_app = FastAPI()

@web_app.post("/add")
async def add(
    source: str = Body(..., description="Source to be added"),
    data_type: str | None = Body(None, description="Type of the data source"),
):
    """
    Adds a new source to the EmbedChain app.
    Expects a JSON with a "source" and "data_type" key.
    "data_type" is optional.
    """
    embedchain_app = get_embedchain_app()
    if source and data_type:
        embedchain_app.add(source, data_type)
    elif source:
        embedchain_app.add(source)
    else:
        return {"message": "No source provided."}
    return {"message": f"Source '{source}' added successfully."}


@web_app.post("/query")
async def query(question: str = Body(..., description="Question to be answered")):
    """
    Handles a query to the EmbedChain app.
    Expects a JSON with a "question" key.
    """
    if not question:
        return {"message": "No question provided."}
    embedchain_app = get_embedchain_app()
    answer = embedchain_app.query(question)
    return {"answer": answer}


@web_app.post("/chat")
async def chat(question: str = Body(..., description="Question to be answered")):
    """
    Handles a chat request to the EmbedChain app.
    Expects a JSON with a "question" key.
    """
    if not question:
        return {"message": "No question provided."}
    embedchain_app = get_embedchain_app()
    response = embedchain_app.chat(question)
    return {"response": response}

# def streamlit_app():
#     import streamlit as st
#     from embedchain import Pipeline as App

#     @st.cache_resource
#     def ec_app():
#         return App.from_config(config={
#             "app": {
#                 "config": {
#                     "name": "open-source-rag-app"
#                 }
#             },
#             "llm": {
#                 "provider": "gpt4all",
#                 "config": {
#                     "model": "mistral-7b-instruct-v0.1.Q4_0.gguf"
#                 }
#             },
#             "embedder": {
#                 "provider": "gpt4all",
#             }
#         })

#     st.title("💬 Chatbot")
#     st.caption("🚀 An Embedchain app powered by Mistral!")
#     if "messages" not in st.session_state:
#         st.session_state.messages = [
#             {
#                 "role": "assistant",
#                 "content": """
#             Hi! I'm a chatbot. I can answer questions and learn new things!\n
#             Ask me anything and if you want me to learn something do `/add <source>`.\n
#             I can learn mostly everything. :)
#             """,
#             }
#         ]

#     for message in st.session_state.messages:
#         with st.chat_message(message["role"]):
#             st.markdown(message["content"])

#     if prompt := st.chat_input("Ask me anything!"):
#         app = ec_app()

#         if prompt.startswith("/add"):
#             with st.chat_message("user"):
#                 st.markdown(prompt)
#                 st.session_state.messages.append({"role": "user", "content": prompt})
#             prompt = prompt.replace("/add", "").strip()
#             with st.chat_message("assistant"):
#                 message_placeholder = st.empty()
#                 message_placeholder.markdown("Adding to knowledge base...")
#                 app.add(prompt)
#                 message_placeholder.markdown(f"Added {prompt} to knowledge base!")
#                 st.session_state.messages.append({"role": "assistant", "content": f"Added {prompt} to knowledge base!"})
#                 st.stop()

#         with st.chat_message("user"):
#             st.markdown(prompt)
#             st.session_state.messages.append({"role": "user", "content": prompt})

#         with st.chat_message("assistant"):
#             msg_placeholder = st.empty()
#             msg_placeholder.markdown("Thinking...")
#             full_response = ""

#             for response in app.chat(prompt):
#                 msg_placeholder.empty()
#                 full_response += response

#             msg_placeholder.markdown(full_response)
#             st.session_state.messages.append({"role": "assistant", "content": full_response})
    

@web_app.get("/")
async def root():
    return responses.RedirectResponse(url="/docs")

@stub.function(image=image)
@asgi_app()
def fastapi_app():
    return web_app
