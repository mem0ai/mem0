# syntax=docker.io/docker/dockerfile:1

# Base stage for common setup
FROM swr.cn-north-4.myhuaweicloud.com/ddn-k8s/docker.io/library/node:18-alpine AS base

ARG ALPINE_MIRROR=https://mirrors.aliyun.com/alpine
ARG NPM_REGISTRY=https://registry.npmmirror.com
ARG PNPM_VERSION=10.5.2

ENV npm_config_registry=${NPM_REGISTRY}

# Install dependencies for pnpm
RUN sed -i "s|https://dl-cdn.alpinelinux.org/alpine|${ALPINE_MIRROR}|g" /etc/apk/repositories && \
    apk add --no-cache libc6-compat curl && \
    npm install -g pnpm@${PNPM_VERSION}

WORKDIR /app

FROM base AS deps

COPY package.json pnpm-lock.yaml ./

RUN pnpm install --frozen-lockfile

FROM base AS builder
WORKDIR /app

COPY --from=deps /app/node_modules ./node_modules
COPY --from=deps /app/pnpm-lock.yaml ./pnpm-lock.yaml
COPY . .

RUN cp next.config.dev.mjs next.config.mjs
RUN cp .env.example .env
RUN NODE_OPTIONS=--max-old-space-size=1024 NEXT_TELEMETRY_DISABLED=1 pnpm build

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

EXPOSE 53000
ENV PORT=53000
ENV HOSTNAME="0.0.0.0"

ENTRYPOINT ["/home/nextjs/entrypoint.sh"]
CMD ["node", "server.js"]
