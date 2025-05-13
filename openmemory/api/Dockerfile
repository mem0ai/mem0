FROM python:3.12-slim

WORKDIR /usr/src/openmemory

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

EXPOSE 8765
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8765"]
