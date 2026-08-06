FROM python:3.11-slim

# tesseract  = OCR + the searchable PDF layer
# poppler     = PDF text extraction and page rendering
# libheif     = iPhone HEIC photos
# libglib     = the one shared library opencv-python-headless still links against
RUN apt-get update && apt-get install -y --no-install-recommends \
        tesseract-ocr tesseract-ocr-deu tesseract-ocr-eng \
        poppler-utils libheif1 libglib2.0-0 \
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
