FROM python:3.12-slim-bookworm

WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
    && apt-get clean && \
    rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Install 3rd-party deps from pre-exported requirements
COPY dist/requirements.txt /tmp/dist/requirements.txt
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --system -r /tmp/dist/requirements.txt

# Install Playwright Chromium + system deps
RUN playwright install chromium --with-deps

# Install project wheel (no-deps: everything already installed above)
COPY dist/*.whl /tmp/dist/
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --system --no-deps /tmp/dist/*.whl \
    && rm -rf /tmp/dist

EXPOSE 8000

CMD ["uvicorn", "download_app.main:app", "--host", "0.0.0.0", "--port", "8000"]
