.PHONY: help up down logs shell migrate test test-clean env ui-install ui-start ui-dev ui-build ui-dev-start

NEXT_PUBLIC_USER_ID=$(USER)
NEXT_PUBLIC_API_URL=http://localhost:8765

# 国内镜像源配置（可根据需求调整）
# Python/pip 镜像：清华 PyPI 镜像
PIP_MIRROR=https://pypi.tuna.tsinghua.edu.cn/simple
# Node/pnpm 镜像：阿里云 npm 镜像
PNPM_REGISTRY=https://registry.npmmirror.com

# Default target
help:
	@echo "Available commands:"
	@echo "  make env       - Copy .env.example to .env"
	@echo "  make up        - Start the containers"
	@echo "  make down      - Stop the containers"
	@echo "  make logs      - Show container logs"
	@echo "  make shell     - Open a shell in the api container"
	@echo "  make migrate   - Run database migrations"
	@echo "  make test      - Run tests in a new container"
	@echo "  make test-clean - Run tests and clean up volumes"
	@echo "  make ui-install - Install frontend dependencies (with mirror)"
	@echo "  make ui-start  - Start the frontend development server"
	@echo "  make ui-dev    - Install dependencies (with mirror) and start frontend in dev mode"
	@echo "  make ui        - Install dependencies (with mirror) and start frontend in production mode"

env:
	cd api && cp .env.example .env
	cd ui && cp .env.example .env

# 构建镜像时，为 pip 配置国内镜像（通过 build-arg 注入）
build:
	docker compose build --build-arg PIP_MIRROR=$(PIP_MIRROR)

# 启动容器时，传递 pip 镜像环境变量（确保容器内 pip 优先使用镜像）
up:
	NEXT_PUBLIC_USER_ID=$(USER) NEXT_PUBLIC_API_URL=$(NEXT_PUBLIC_API_URL) PIP_MIRROR=$(PIP_MIRROR) docker compose up

down:
	docker compose down -v
	rm -f api/openmemory.db

logs:
	docker compose logs -f

shell:
	docker compose exec api bash

# 容器内执行 pip 相关命令时，通过 --index-url 指定镜像
upgrade:
	docker compose exec api pip install --upgrade pip --index-url $(PIP_MIRROR) && \
	docker compose exec api alembic upgrade head

migrate:
	docker compose exec api pip install --upgrade pip --index-url $(PIP_MIRROR) && \
	docker compose exec api alembic upgrade head

downgrade:
	docker compose exec api alembic downgrade -1

# 前端安装依赖：先配置 pnpm 镜像，再执行安装
ui-install:
	cd ui && \
	pnpm config set registry $(PNPM_REGISTRY) && \
	pnpm install --frozen-lockfile

ui-start:
	cd ui && NEXT_PUBLIC_USER_ID=$(USER) NEXT_PUBLIC_API_URL=$(NEXT_PUBLIC_API_URL) pnpm dev

# 前端开发模式：整合镜像配置+依赖安装+启动
ui-dev:
	cd ui && \
	pnpm config set registry $(PNPM_REGISTRY) && \
	NEXT_PUBLIC_USER_ID=$(USER) NEXT_PUBLIC_API_URL=$(NEXT_PUBLIC_API_URL) pnpm install --frozen-lockfile && \
	pnpm dev

# （补充）前端生产模式：镜像配置+依赖安装+构建（如需）
ui:
	cd ui && \
	pnpm config set registry $(PNPM_REGISTRY) && \
	NEXT_PUBLIC_USER_ID=$(USER) NEXT_PUBLIC_API_URL=$(NEXT_PUBLIC_API_URL) pnpm install --frozen-lockfile && \
	pnpm build && \
	pnpm start