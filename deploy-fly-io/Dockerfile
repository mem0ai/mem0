# OpenMemory Fly.io Deployment Dockerfile
# Optimized for production with security hardening

FROM python:3.12-slim AS builder

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

# Copy only requirements first for better caching
COPY openmemory/api/requirements.txt ./api-requirements.txt
COPY deploy-fly-io/api/requirements-extra.txt ./extra-requirements.txt

# Create virtual environment and install dependencies
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r api-requirements.txt && \
    pip install --no-cache-dir -r extra-requirements.txt

# Production image
FROM python:3.12-slim AS production

# Security: Run as non-root user with home directory
RUN groupadd -r openmemory && useradd -r -g openmemory -m -d /home/openmemory openmemory

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    sqlite3 \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /app

# Copy application code
COPY openmemory/api/ ./
COPY deploy-fly-io/api/auth_middleware.py ./
COPY deploy-fly-io/api/http_transport.py ./
COPY deploy-fly-io/api/startup.py ./

# Create data directories with proper permissions
RUN mkdir -p /data/qdrant /data/sqlite && \
    chown -R openmemory:openmemory /data /app /home/openmemory

# Switch to non-root user
USER openmemory

# Environment
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app \
    HOME=/home/openmemory

EXPOSE 8765

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8765/health || exit 1

# Start with our custom startup script
CMD ["python", "startup.py"]
