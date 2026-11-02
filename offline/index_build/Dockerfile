FROM ghcr.io/astral-sh/uv:0.9.22 AS uv
FROM python:3.13-slim

COPY --from=uv /uv /usr/local/bin/uv
WORKDIR /app
ENV UV_PYTHON_DOWNLOADS=never \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    HF_HUB_DISABLE_PROGRESS_BARS=1 \
    GRAPHIV_SQLITE_WRITE_VFS=unix-dotfile \
    OMP_NUM_THREADS=4 \
    OPENBLAS_NUM_THREADS=4 \
    PATH=/app/.venv/bin:$PATH

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project --group index-build

COPY src ./src
COPY offline/__init__.py ./offline/__init__.py
COPY offline/index_build ./offline/index_build
COPY configs ./configs

ENTRYPOINT ["python", "-m", "offline.index_build.run_hf"]
