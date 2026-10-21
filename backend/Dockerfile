FROM python:3.14-slim AS builder

# biotraj, a biotite dependency, ships only a source package for Python 3.14, so it is compiled here
# and the final image carries no compiler.
RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc libc6-dev \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.13.0 /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app

# Dependencies first so code changes don't invalidate this layer.
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-install-project

COPY src ./src
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-editable

FROM python:3.14-slim

ENV PATH="/app/.venv/bin:$PATH"

WORKDIR /app

COPY --from=builder /app /app

# A new named volume takes the owner of the directory it is mounted on, so the store's volume on a
# server (docker-compose.coolify.yaml) is writable by this user.
RUN useradd --create-home --uid 1000 molecula \
    && mkdir /data \
    && chown molecula /data
USER molecula

EXPOSE 8000
CMD ["uvicorn", "molecula.main:app", "--host", "0.0.0.0", "--port", "8000"]
