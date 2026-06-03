FROM python:3.11-slim

WORKDIR /app

RUN pip install --upgrade pip

COPY packages/recommendation_module/backend/requirements.txt /app/requirements.txt
RUN pip install --default-timeout=100 --retries 10 --no-cache-dir -r /app/requirements.txt

COPY packages/recommendation_module/backend /app

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]