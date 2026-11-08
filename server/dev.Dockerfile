FROM python:3.12-slim

# Keep the editable SDK outside /app: Compose mounts server/ at /app.
WORKDIR /opt/mem0
COPY pyproject.toml README.md LICENSE ./
COPY mem0 ./mem0
COPY server/requirements.txt /tmp/server-requirements.txt
RUN pip install --no-cache-dir -r /tmp/server-requirements.txt -e '.[graph]'

WORKDIR /app
COPY server .

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
