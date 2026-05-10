FROM python:3.11-slim
WORKDIR /app
COPY common ./common
COPY scripts ./scripts
RUN pip install --no-cache-dir sqlalchemy psycopg2-binary
CMD ["python", "scripts/fake_detections.py", "--full", "--days", "7"]
