# syntax=docker.io/docker/dockerfile:1

# Base stage for common setup
FROM node:18-alpine AS base

LABEL org.opencontainers.image.name="n1:1024/openmemory-ui"

# Install dependencies for pnpm
    # corepack enable && \
    # corepack prepare pnpm@latest --activate
RUN apk add --no-cache libc6-compat curl && \
    npm config set registry https://registry.npmmirror.com/ && \
    npm install -g pnpm@latest

WORKDIR /app

FROM base AS deps

COPY package.json pnpm-lock.yaml ./

# 配置淘宝源
RUN pnpm config set registry https://registry.npmmirror.com/

RUN pnpm install --frozen-lockfile

FROM base AS builder
WORKDIR /app

COPY --from=deps /app/node_modules ./node_modules
COPY --from=deps /app/pnpm-lock.yaml ./pnpm-lock.yaml
COPY . .

# 确保builder阶段也使用淘宝源
RUN pnpm config set registry https://registry.npmmirror.com/

RUN cp next.config.dev.mjs next.config.mjs
RUN cp .env.example .env
RUN pnpm build

FROM base AS runner
WORKDIR /app

ENV NODE_ENV=production

RUN addgroup --system --gid 1001 nodejs && \
    adduser --system --uid 1001 nextjs

COPY --from=builder /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

COPY --chown=nextjs:nodejs entrypoint.sh /home/nextjs/entrypoint.sh
RUN chmod +x /home/nextjs/entrypoint.sh

USER nextjs

EXPOSE 3000
ENV PORT=3000
ENV HOSTNAME="0.0.0.0"

ENTRYPOINT ["/home/nextjs/entrypoint.sh"]
CMD ["node", "server.js"]
