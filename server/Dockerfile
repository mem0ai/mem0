FROM python:3.12-slim

# Install PostgreSQL client library (required by psycopg >= 3.x)
# Without libpq-dev, psycopg fails with: "no pq wrapper available. libpq library not found"
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Ensure the SQLite history directory exists and is writable.
# Mem0 defaults HISTORY_DB_PATH to /app/history/history.db and crashes with
# "unable to open database file" if the parent directory is missing.
RUN mkdir -p /app/history && touch /app/history/.keep

EXPOSE 8000

ENV PYTHONUNBUFFERED=1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
