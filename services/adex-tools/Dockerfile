FROM ghcr.io/astral-sh/uv:0.10.9 AS uv
FROM python:3.14-slim-bookworm
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked --mount=type=cache,target=/var/lib/apt/lists,sharing=locked rm -f /etc/apt/apt.conf.d/docker-clean && apt-get -o Acquire::Retries=3 update && apt-get -o Acquire::Retries=3 install -y --no-install-recommends ffmpeg
COPY --from=uv /uv /usr/local/bin/uv
WORKDIR /workspace
COPY packages/python-kernel packages/python-kernel
COPY services/adex-tools services/adex-tools
RUN uv sync --project services/adex-tools --frozen --no-dev && useradd --uid 10001 --create-home adex
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PLAYWRIGHT_BROWSERS_PATH=/opt/adex-browsers
RUN uv run --project services/adex-tools playwright install --with-deps chromium
USER 10001:10001
ENTRYPOINT ["/workspace/services/adex-tools/.venv/bin/uvicorn","adex_tools.main:app","--host","0.0.0.0","--port","8107","--no-access-log"]
