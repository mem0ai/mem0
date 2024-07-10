FROM python:3.11 AS backend

WORKDIR /usr/src/api
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

EXPOSE 5000

ENV FLASK_APP=api_server.py

ENV FLASK_RUN_EXTRA_FILES=/usr/src/api/*
ENV FLASK_ENV=development

CMD ["flask", "run", "--host=0.0.0.0", "--reload"]
