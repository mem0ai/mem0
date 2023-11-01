FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt /app/

RUN pip install --no-cache-dir -r requirements.txt

COPY . /app

EXPOSE 8010

ENV NAME embedchain

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8010"]
