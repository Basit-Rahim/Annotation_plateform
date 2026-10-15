# Production web image: build the React app once, serve it with Caddy.
# Caddy also terminates HTTPS and proxies /api to the API container, so the
# UI and API share one origin (no CORS, first-party session cookie).
# Build context: ./frontend (see docker-compose.prod.yml).

FROM node:20-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY . .
# Empty = same origin: the client calls /api/... relative to the page.
ARG VITE_API_BASE_URL=""
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}
RUN npm run build

FROM caddy:2.8-alpine
COPY --from=build /app/dist /srv
