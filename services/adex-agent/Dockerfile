FROM ghcr.io/astral-sh/uv:0.10.9 AS uv
FROM python:3.12-slim
COPY --from=uv /uv /usr/local/bin/uv
WORKDIR /workspace
COPY packages/python-kernel packages/python-kernel
COPY services/adex-agent services/adex-agent
RUN uv sync --project services/adex-agent --frozen --no-dev && useradd --uid 10001 --create-home adex
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
USER 10001:10001
ENTRYPOINT ["/workspace/services/adex-agent/.venv/bin/uvicorn","adex_agent.main:app","--host","0.0.0.0","--port","8105","--no-access-log"]
