FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt requirements-ai.txt requirements-ocr.txt ./
RUN pip install --no-cache-dir -r requirements.txt \
    -r requirements-ai.txt \
    -r requirements-ocr.txt

COPY src/ ./src/
COPY scripts/download-yolo-model.sh ./scripts/
RUN chmod +x scripts/download-yolo-model.sh && ./scripts/download-yolo-model.sh

RUN mkdir -p logs storage/frames storage/events models sites

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

EXPOSE 8080

CMD ["python", "-m", "src.main"]
