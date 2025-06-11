from fastapi import FastAPI, responses
from pydantic import BaseModel

from embedchain import App

app = FastAPI(title="Embedchain FastAPI App")
embedchain_app = App()


class SourceModel(BaseModel):
    source: str


class QuestionModel(BaseModel):
    question: str


@app.post("/add")
async def add_source(source_model: SourceModel):
    """
    Adds a new source to the EmbedChain app.
    Expects a JSON with a "source" key.
    """
    source = source_model.source
    embedchain_app.add(source)
    return {"message": f"Source '{source}' added successfully."}


@app.post("/query")
async def handle_query(question_model: QuestionModel):
    """
    Handles a query to the EmbedChain app.
    Expects a JSON with a "question" key.
    """
    question = question_model.question
    answer = embedchain_app.query(question)
    return {"answer": answer}


@app.post("/chat")
async def handle_chat(question_model: QuestionModel):
    """
    Handles a chat request to the EmbedChain app.
    Expects a JSON with a "question" key.
    """
    question = question_model.question
    response = embedchain_app.chat(question)
    return {"response": response}


@app.get("/")
async def root():
    return responses.RedirectResponse(url="/docs")
