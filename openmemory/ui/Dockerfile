# syntax=docker.io/docker/dockerfile:1

# Base stage for common setup
FROM node:18-alpine AS base

# Install dependencies for pnpm
RUN apk add --no-cache libc6-compat curl && \
    corepack enable && \
    corepack prepare pnpm@latest --activate

WORKDIR /app

# Dependencies stage
FROM base AS deps

# Copy lockfile and manifest
COPY package.json pnpm-lock.yaml ./

# Install dependencies using pnpm
RUN pnpm install --frozen-lockfile

# Builder stage
FROM base AS builder
WORKDIR /app

COPY --from=deps /app/node_modules ./node_modules
COPY --from=deps /app/pnpm-lock.yaml ./pnpm-lock.yaml
COPY . .

RUN cp next.config.dev.mjs next.config.mjs
RUN cp .env.dev .env

RUN pnpm build

# Production runner stage
FROM base AS runner
WORKDIR /app

ENV NODE_ENV=production

# Create non-root user for security
RUN addgroup --system --gid 1001 nodejs && \
    adduser --system --uid 1001 nextjs

# Copy production dependencies and built artifacts
COPY --from=builder /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

# Copy and prepare entrypoint script
COPY --chown=nextjs:nodejs entrypoint.sh /home/nextjs/entrypoint.sh
RUN chmod +x /home/nextjs/entrypoint.sh

# Switch to non-root user
USER nextjs

EXPOSE 3000
ENV PORT=3000
ENV HOSTNAME="0.0.0.0"

ENTRYPOINT ["/home/nextjs/entrypoint.sh"]
CMD ["node", "server.js"]
