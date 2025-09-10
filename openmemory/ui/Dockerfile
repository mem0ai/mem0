# syntax=docker.io/docker/dockerfile:1

# Base stage for common setup（基础环境：配置 pnpm 镜像）
FROM node:18-alpine AS base

# 接收 docker-compose 传递的 PNPM_REGISTRY 参数（默认阿里云镜像）
ARG PNPM_REGISTRY=${PNPM_REGISTRY:-https://registry.npmmirror.com}

# 1. 安装依赖 + 配置 corepack（pnpm 包管理）
# 2. 优先设置 pnpm 镜像（避免后续安装走官方源）
RUN apk add --no-cache libc6-compat curl && \
    corepack enable && \
    corepack prepare pnpm@latest --activate && \
    # 配置 pnpm 镜像（全局生效，覆盖所有阶段）
    pnpm config set registry ${PNPM_REGISTRY} && \
    # 可选：配置 node-sass 等二进制依赖的国内镜像（解决编译依赖下载慢）
    pnpm config set sass_binary_site https://npmmirror.com/mirrors/node-sass/ && \
    pnpm config set electron_mirror https://npmmirror.com/mirrors/electron/

WORKDIR /app

# Deps stage（依赖安装：复用 base 阶段的镜像配置）
FROM base AS deps

# 复制依赖清单（仅复制 package.json 和 lockfile，利用 Docker 缓存）
COPY package.json pnpm-lock.yaml ./

# 安装依赖：--frozen-lockfile 确保版本与 lockfile 一致，避免依赖漂移
# 因 base 阶段已配置镜像，此处直接执行 pnpm install 即可加速
RUN pnpm install --frozen-lockfile

# Builder stage（构建阶段：复用 deps 阶段的依赖，无需重新配置镜像）
FROM base AS builder
WORKDIR /app

# 从 deps 阶段复制已安装的依赖（避免重复下载）
COPY --from=deps /app/node_modules ./node_modules
COPY --from=deps /app/pnpm-lock.yaml ./pnpm-lock.yaml
# 复制项目源码
COPY . .

# 执行构建前的配置（复制开发环境配置、示例 env）
RUN cp next.config.dev.mjs next.config.mjs && \
    cp .env.example .env

# 构建项目（依赖已安装，直接构建）
RUN pnpm build

# Runner stage（运行阶段：仅保留构建产物，最小化镜像体积）
FROM base AS runner
WORKDIR /app

# 配置生产环境变量
ENV NODE_ENV=production

# 创建非 root 用户（安全最佳实践）
RUN addgroup --system --gid 1001 nodejs && \
    adduser --system --uid 1001 nextjs

# 从 builder 阶段复制构建产物（仅复制必要文件，减少镜像体积）
COPY --from=builder /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

# 复制启动脚本并授权
COPY --chown=nextjs:nodejs entrypoint.sh /home/nextjs/entrypoint.sh
RUN chmod +x /home/nextjs/entrypoint.sh

# 切换到非 root 用户运行
USER nextjs

# 暴露端口
EXPOSE 3000
ENV PORT=3000
ENV HOSTNAME="0.0.0.0"

# 启动命令
ENTRYPOINT ["/home/nextjs/entrypoint.sh"]
CMD ["node", "server.js"]