FROM python:3.12-slim
RUN pip install --no-cache-dir "psycopg[binary]==3.2.6" && useradd --uid 10001 --create-home adex
WORKDIR /workspace
COPY scripts/config.py scripts/migrate.py scripts/
COPY migrations migrations
USER 10001:10001
CMD ["python","scripts/migrate.py"]
