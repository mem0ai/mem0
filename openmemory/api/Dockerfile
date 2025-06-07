FROM python:3.12-slim

LABEL org.opencontainers.image.name="n1:1024/openmemory-mcp"

WORKDIR /usr/src/openmemory

COPY requirements.txt .
RUN pip install -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple/

COPY config.json .
COPY . .

EXPOSE 8765
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8765"]
