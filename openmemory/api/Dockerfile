FROM python:3.12-slim

LABEL org.opencontainers.image.name="mem0/openmemory-mcp"


WORKDIR /usr/src/openmemory

COPY requirements.txt .
# COPY ../../mem0 /usr/src/openmemory
RUN pip install -r requirements.txt

COPY config.json .
COPY . .

EXPOSE 8050
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8050", "--timeout-keep-alive", "120"]
