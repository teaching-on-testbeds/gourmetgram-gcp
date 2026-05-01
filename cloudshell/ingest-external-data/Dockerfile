FROM python:3.11-slim
RUN pip install --no-cache-dir google-cloud-storage
WORKDIR /app
COPY ingest_food11.py /app/ingest_food11.py
CMD ["python", "/app/ingest_food11.py"]
