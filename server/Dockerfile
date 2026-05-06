FROM python:3.12-slim

# Install native library required by psycopg (PostgreSQL adapter)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=app:app . .

# Create a non-root user for security
RUN adduser --disabled-password --gecos "" app && \
    chown -R app:app /app

USER app

EXPOSE 8000

ENV PYTHONUNBUFFERED=1

# Note: do NOT add --reload here; it is development-only behavior.
# For development, use docker-compose.yaml which overrides this CMD with --reload.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]

