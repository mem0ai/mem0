FROM python:3.12-slim

# Build from the repository root so the API uses this checkout's SDK.
WORKDIR /opt/mem0
COPY pyproject.toml README.md LICENSE ./
COPY mem0 ./mem0
COPY server/requirements.txt /tmp/server-requirements.txt
RUN pip install --no-cache-dir -r /tmp/server-requirements.txt .

WORKDIR /app
COPY server .

EXPOSE 8000
ENV PYTHONUNBUFFERED=1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
