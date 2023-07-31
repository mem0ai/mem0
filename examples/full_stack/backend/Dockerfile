FROM python:3.11 AS backend

WORKDIR /usr/src/app/backend
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["python", "server.py"]
