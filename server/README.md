# Mem0 FastAPI Server

This repository provides a FastAPI server that exposes the functionality of [Mem0](https://github.com/mem0ai/mem0). Users can perform all operations (store, retrieve, search, update, view history, delete, and reset memories) through REST endpoints. The API also includes OpenAPI documentation, which can be accessed at `/docs` when the server is running.

## Features

- **Add Memory:** Store a new memory for a user.
- **Retrieve Memories:** Get all memories for a given user or a specific memory by its ID.
- **Search Memories:** Search stored memories based on a query.
- **Update Memory:** Update an existing memory.
- **Memory History:** View the history of a memory.
- **Delete Memory:** Delete a specific memory or all memories for a user.
- **Reset Memory:** Reset all memories.
- **OpenAPI Documentation:** Accessible via `/docs` endpoint.

## Running Locally

### Prerequisites

- Python 3.9+
- [pip](https://pip.pypa.io/)

### Installation

1. Clone this repository:
   ```bash
   git clone https://github.com/your-username/mem0-fastapi-server.git
   cd mem0-fastapi-server

2. Create a `.env` file in the root directory of the project and set your environment variables. For example:

```env
OPENAI_API_KEY=your-openai-api-key
```

3. Install dependencies:

```bash
pip install -r requirements.txt
```

4. Start the FastAPI server:

```bash
uvicorn main:app --reload
```

Visit http://localhost:8000/docs to see the OpenAPI documentation.

### Running with Docker

1. Create a `.env` file in the root directory of the project and set your environment variables. For example:

```env
OPENAI_API_KEY=your-openai-api-key
```

2. Build the Docker image:

```bash
docker build -t mem0-api-server .
```

3. Run the Docker container:

``` bash
docker run -p 8000:8000 mem0-api-server
```

4. Access the API at http://localhost:8000.


### Usage

Once the server is running (locally or via Docker), you can interact with it using any REST client or through your preferred programming language (e.g., Go, Java, etc.). For example, to add a new memory:

```bash
curl -X POST "http://localhost:8000/memories" \
     -H "Content-Type: application/json" \
     -d '{"memory": "Likes to play cricket on weekends", "user_id": "alice", "metadata": {"category": "hobbies"}}'
```

This will add a new memory with the specified details. You can also use the other endpoints (GET, PUT, DELETE, etc.) similarly.
