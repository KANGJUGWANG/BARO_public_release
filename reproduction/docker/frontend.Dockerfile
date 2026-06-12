FROM node:22.12-alpine AS build

WORKDIR /app/frontend
ENV VITE_BACKEND_URL=/api

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build

FROM nginx:1.27-alpine

COPY reproduction/nginx/default.conf.template /etc/nginx/conf.d/default.conf
COPY --from=build /app/frontend/dist /usr/share/nginx/html

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD wget -qO- http://localhost/__frontend_health >/dev/null || exit 1
