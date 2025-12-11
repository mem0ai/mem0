FROM python:3.12-slim

LABEL org.opencontainers.image.name="mem0/openmemory-mcp"

WORKDIR /usr/src/openmemory

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY config.json .
COPY . .

EXPOSE 8765
CMD ["sh", "-c", "alembic stamp add_prompts_table 2>/dev/null || true && alembic upgrade head && uvicorn main:app --host 0.0.0.0 --port 8765"]
