FROM python:3.11-slim
RUN pip install --no-cache-dir google-cloud-storage
WORKDIR /app
COPY prepare_training_dataset.py /app/prepare_training_dataset.py
CMD ["python", "/app/prepare_training_dataset.py"]
