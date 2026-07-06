FROM python:3.11-slim
RUN pip install --no-cache-dir docker httpx
COPY shipper.py /app/shipper.py
WORKDIR /app
CMD ["python", "shipper.py"]
