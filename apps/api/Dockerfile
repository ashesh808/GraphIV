FROM ghcr.io/astral-sh/uv:0.9.22 AS uv
FROM python:3.13-slim

COPY --from=uv /uv /usr/local/bin/uv
WORKDIR /app

ENV UV_PYTHON_DOWNLOADS=never \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    GRAPHIV_CONFIG=/app/configs/runtime.toml \
    PATH=/app/.venv/bin:$PATH

COPY pyproject.toml uv.lock README.md LICENSE ./
COPY src ./src
COPY apps/__init__.py ./apps/__init__.py
COPY apps/api ./apps/api
COPY legacy/research-webui ./legacy/research-webui
COPY retrieval_recipes ./retrieval_recipes
COPY configs/runtime.toml ./configs/runtime.toml

RUN uv sync --frozen --no-dev --no-editable

EXPOSE 8000
CMD ["graphiv-serve", "--http", "--role", "api", "--host", "0.0.0.0", "--port", "8000"]
