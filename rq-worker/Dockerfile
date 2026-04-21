FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 libxcb1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY common ./common
COPY worker/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY worker/ ./worker/
COPY eyegila_v3.pt ./eyegila_v3.pt

CMD ["rq", "worker", "video", "--url", "redis://redis:6379", "--path", "/app"]
