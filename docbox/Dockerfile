FROM python:3.11-slim

# tesseract = OCR for scans, poppler = PDF text + page rendering, libheif = iPhone photos
RUN apt-get update && apt-get install -y --no-install-recommends \
        tesseract-ocr tesseract-ocr-deu tesseract-ocr-eng \
        poppler-utils libheif1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /srv/docbox

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY web ./web

ENV DOCBOX_DATA_DIR=/data \
    DOCBOX_OLLAMA_URL=http://ollama:11434 \
    PYTHONUNBUFFERED=1

VOLUME ["/data"]
EXPOSE 8484

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8484"]
