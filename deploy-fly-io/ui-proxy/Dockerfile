FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir fastapi uvicorn httpx itsdangerous python-multipart

COPY proxy.py .

EXPOSE 3001

CMD ["python", "proxy.py"]
