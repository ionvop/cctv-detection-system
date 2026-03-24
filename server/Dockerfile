FROM python:3.11-slim
WORKDIR /app
COPY common ./common
COPY server/requirements.txt .
RUN pip install -r requirements.txt
COPY server/ .
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]