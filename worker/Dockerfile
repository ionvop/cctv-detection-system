FROM python:3.11-slim
WORKDIR /app
COPY common ./common
COPY worker/requirements.txt .
RUN pip install -r requirements.txt
COPY worker/ .
CMD ["python", "main.py"]
