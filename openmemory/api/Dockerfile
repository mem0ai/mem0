FROM python:3.12-slim

LABEL org.opencontainers.image.name="mem0/openmemory-mcp"

WORKDIR /usr/src/openmemory

# --- START: New lines to install sqlite3 ---
# 1. Update package lists
# 2. Install sqlite3 (the tool) and libsqlite3-dev (needed for many Python libraries)
# 3. Clean up the cache to keep the image small
RUN apt-get update && \
    apt-get install -y sqlite3 libsqlite3-dev && \
    rm -rf /var/lib/apt/lists/*
# --- END: New lines to install sqlite3 ---

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY config.json .
COPY . .

EXPOSE 8765
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8765"]