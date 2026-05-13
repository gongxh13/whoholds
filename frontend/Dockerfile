# whoholds frontend — static build served by Caddy.
FROM node:20-alpine AS builder
WORKDIR /app

# pnpm via corepack (matches AGENTS.md: pnpm + frozen lockfile).
RUN corepack enable && corepack prepare pnpm@10.28.2 --activate

COPY package.json pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile

COPY tsconfig.json vite.config.ts biome.json index.html ./
COPY src ./src
COPY openapi.json ./openapi.json
RUN pnpm build

FROM caddy:2.8-alpine AS runtime
COPY --from=builder /app/dist /srv
# Caddy config lives in the compose volume; this image is just a static
# bundle on top of the official caddy image.
