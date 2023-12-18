from fastapi import FastAPI, Request, responses

from embedchain import Pipeline

# Initialize the FastAPI app and EmbedChain app
app = FastAPI()
embedchain_app = Pipeline()


@app.post("/add")
async def add_source(request: Request):
    """
    Adds a new source to the EmbedChain app.
    Expects a JSON with a "source" key.
    """
    data = await request.json()
    source = data.get("source")
    embedchain_app.add(source)
    return {"message": f"Source '{source}' added successfully."}


@app.post("/query")
async def handle_query(request: Request):
    """
    Handles a query to the EmbedChain app.
    Expects a JSON with a "question" key.
    """
    data = await request.json()
    question = data.get("question")
    answer = embedchain_app.query(question)
    return {"answer": answer}


@app.post("/chat")
async def handle_chat(request: Request):
    """
    Handles a chat request to the EmbedChain app.
    Expects a JSON with a "question" key.
    """
    data = await request.json()
    question = data.get("question")
    response = embedchain_app.chat(question)
    return {"response": response}


@app.get("/")
async def root():
    return responses.RedirectResponse(url="/docs")
