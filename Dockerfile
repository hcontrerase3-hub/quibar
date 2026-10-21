FROM node:22-bookworm-slim AS frontend
WORKDIR /src
COPY package.json package-lock.json ./
RUN npm ci
COPY index.html tsconfig.json vite.config.ts vitest.config.ts postcss.config.mjs ./
COPY app app
COPY components components
COPY lib lib
COPY public public
COPY vendor vendor
RUN npm run build

FROM python:3.12-slim-bookworm AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY backend/requirements.lock backend/requirements.lock
RUN pip install -r backend/requirements.lock \
    && groupadd -g 10001 quibar && useradd -u 10001 -g quibar quibar \
    && mkdir -p /state/media /run/quibar && chown -R quibar:quibar /state /run/quibar
COPY backend backend
COPY alembic.ini ./
COPY data/catalog.json data/catalog.json
COPY --from=frontend /src/dist dist
USER 10001:10001
CMD ["python", "-m", "backend.container_ops", "serve"]
