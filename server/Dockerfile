FROM python:3.11-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 libxcb1 \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY common ./common
COPY server/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY server ./server
COPY worker ./worker
CMD ["uvicorn", "server.main:app", "--host", "0.0.0.0", "--port", "8000"]
