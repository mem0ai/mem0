FROM python:3.11 AS backend

WORKDIR /usr/src/api
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

EXPOSE 5000

CMD ["python", "api_server.py"]
