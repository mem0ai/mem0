build:
	docker build -t mem0-api-server .

run_local:
	docker run -p 8000:8000 -v $(shell pwd):/app mem0-api-server --env-file .env

.PHONY: build run_local
