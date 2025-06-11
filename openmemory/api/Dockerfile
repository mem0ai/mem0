FROM python:3.12-slim

LABEL org.opencontainers.image.name="mem0/openmemory-api"

WORKDIR /usr/src/app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Ensure the app module is in the Python path
ENV PYTHONPATH=/usr/src/app

EXPOSE 8765

# Default command (can be overridden by docker-compose)
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8765"]
