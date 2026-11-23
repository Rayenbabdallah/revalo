# Revalo web app, served by Caddy, which also proxies /api to the API container.
FROM node:24-alpine AS build
RUN npm install -g pnpm@10
WORKDIR /web
COPY package.json pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile
COPY . .
RUN pnpm build

FROM caddy:2-alpine
COPY Caddyfile /etc/caddy/Caddyfile
COPY --from=build /web/dist /srv
