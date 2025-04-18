build:
	docker build -t mem0-api-server .

run_local:
	docker run --env-file .env \
		-p 8000:8000 \
		--add-host=localhost:172.17.0.1 \
		-v "$(shell pwd):/app" \
		mem0-api-server

.PHONY: build run_local
