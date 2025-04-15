FROM python:3.12

WORKDIR /app

# Install Poetry
RUN curl -sSL https://install.python-poetry.org | python3 -
ENV PATH="/root/.local/bin:$PATH"

# Copy requirements first for better caching
COPY server/requirements.txt .
RUN pip install -r requirements.txt

# Install mem0 in editable mode using Poetry
WORKDIR /app/packages
COPY pyproject.toml .
COPY poetry.lock .
COPY README.md .
COPY mem0 ./mem0
RUN pip install -e .[graph]

# Return to app directory and copy server code
WORKDIR /app
COPY server .

ENV SERVER_WORKER_AMOUNT=-1

# In development, live reloading is enabled so workers will not be applied.
CMD ["sh", "-c", "if [ \"$SERVER_WORKER_AMOUNT\" != \"-1\" ]; then echo \"Warning: --workers option is ignored in reload mode\"; fi; exec uvicorn main:app --host 0.0.0.0 --port 8000 --reload"]
