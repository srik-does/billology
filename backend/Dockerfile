FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1

# System deps: Tesseract (fallback image OCR), Poppler (PDF rasterization for
# scanned PDFs), and libgl1/libglib2.0-0 (required by opencv-python, which
# RapidOCR — the primary OCR engine — imports; absent from slim base images).
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        tesseract-ocr poppler-utils libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

# Bake the RapidOCR models (det + en rec) into the image at build time. They
# are otherwise fetched from a ModelScope CDN on first use, which must not
# happen at runtime (cold-start latency and an unreliable external dependency).
RUN python -c "from rapidocr import LangRec, RapidOCR; RapidOCR(params={'Rec.lang_type': LangRec.EN, 'Global.use_cls': False})"

COPY . .

EXPOSE 8000

# Hosts (Render/Railway/Fly) inject $PORT; default to 8000 locally.
CMD ["sh", "-c", "uvicorn src.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
