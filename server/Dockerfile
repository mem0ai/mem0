FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

ENV PYTHONUNBUFFERED=1
ENV SERVER_WORKER_AMOUNT=-1

CMD ["sh", "-c", "if [ \"$SERVER_WORKER_AMOUNT\" = \"-1\" ]; then workers=$(getconf _NPROCESSORS_ONLN); else workers=$SERVER_WORKER_AMOUNT; fi; exec uvicorn main:app --host 0.0.0.0 --port 8000 --workers $workers"]
