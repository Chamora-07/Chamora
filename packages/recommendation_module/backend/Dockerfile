FROM python:3.11-slim

WORKDIR /app

RUN pip install --upgrade pip

COPY packages/recommendation_module/backend/requirements.txt /app/requirements.txt
RUN pip install --default-timeout=100 --retries 10 --no-cache-dir -r /app/requirements.txt

# Pre-download the ONNX model into /app/model_cache before the source COPY so
# the layer is preserved. The app reads from this same path at runtime.
# HF_HUB_DISABLE_SYMLINKS_WARNING suppresses the Linux symlink advisory.
ENV FASTEMBED_CACHE_PATH=/app/model_cache \
    HF_HUB_DISABLE_SYMLINKS_WARNING=1
RUN python -c "from fastembed import TextEmbedding; TextEmbedding('sentence-transformers/all-MiniLM-L6-v2')"

COPY packages/recommendation_module/backend /app

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]