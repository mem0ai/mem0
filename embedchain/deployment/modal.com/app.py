from dotenv import load_dotenv
from fastapi import Body, FastAPI, responses
from modal import Image, Secret, Stub, asgi_app

from embedchain import App

load_dotenv(".env")

image = Image.debian_slim().pip_install(
    "embedchain",
    "embedchain[dataloaders]",
)

stub = Stub(
    name="embedchain-app",
    image=image,
    secrets=[Secret.from_dotenv(".env")],
)

web_app = FastAPI()
embedchain_app = App(name="embedchain-modal-app")


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
    answer = embedchain_app.query(question)
    return {"answer": answer}


@web_app.get("/chat")
async def chat(question: str = Body(..., description="Question to be answered")):
    """
    Handles a chat request to the EmbedChain app.
    Expects a JSON with a "question" key.
    """
    if not question:
        return {"message": "No question provided."}
    response = embedchain_app.chat(question)
    return {"response": response}


@web_app.get("/")
async def root():
    return responses.RedirectResponse(url="/docs")


@stub.function(image=image)
@asgi_app()
def fastapi_app():
    return web_app
