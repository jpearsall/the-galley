FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

FROM python:3.12-slim
WORKDIR /app
COPY --from=builder /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"
COPY schema ./schema
COPY scripts ./scripts
COPY data ./data
# GALLEY_DATA is overridden to /data/galley-data.json by the CronJob (PVC mount)
ENTRYPOINT ["python", "scripts/generate.py"]
