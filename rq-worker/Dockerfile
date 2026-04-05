FROM python:3.11-slim
WORKDIR /app
COPY common ./common
COPY rq-worker/requirements.txt .
RUN pip install -r requirements.txt
CMD ["rq", "worker", "--url", "redis://redis:6379"]
