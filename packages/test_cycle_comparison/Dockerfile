FROM python:3.11-slim

WORKDIR /app

RUN pip install --upgrade pip

COPY packages/test_cycle_comparison/requirements.txt /app/requirements.txt
RUN pip install --default-timeout=100 --retries 10 --no-cache-dir -r /app/requirements.txt

COPY packages/test_cycle_comparison /app

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
