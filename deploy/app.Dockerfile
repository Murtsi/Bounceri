# Yksi image kaikille Python-palveluille (demosivu, worker, API) + käännetty dashboard.

FROM node:20.17.0-bookworm-slim AS frontend
WORKDIR /fe
RUN corepack enable && corepack prepare pnpm@9.15.0 --activate
COPY frontend/package.json frontend/pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile
COPY frontend/ ./
RUN pnpm run build

FROM ghcr.io/astral-sh/uv:0.8.22-python3.12-bookworm-slim
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project
COPY src ./src
COPY models ./models
COPY deploy/traps.txt ./deploy/traps.txt
RUN uv sync --frozen --no-dev
COPY --from=frontend /fe/dist ./frontend/dist
EXPOSE 8000 8001
CMD ["uv", "run", "--no-sync", "uvicorn", "bouncer.site.app:app", "--host", "0.0.0.0", "--port", "8000"]
