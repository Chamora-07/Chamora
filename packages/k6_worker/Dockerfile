FROM python:3.12-slim

RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    librdkafka-dev \
    && rm -rf /var/lib/apt/lists/*

RUN wget -q https://github.com/grafana/k6/releases/download/v0.54.0/k6-v0.54.0-linux-amd64.tar.gz \
    && tar -xzf k6-v0.54.0-linux-amd64.tar.gz \
    && mv k6-v0.54.0-linux-amd64/k6 /usr/local/bin/k6 \
    && rm -rf k6-v0.54.0-linux-amd64*

RUN k6 version

WORKDIR /app

ENV PYTHONUNBUFFERED=1

RUN pip3 install --no-cache-dir \
    confluent-kafka==2.4.0 \
    sqlalchemy[asyncio]==2.0.30 \
    asyncpg==0.29.0 \
    python-dotenv==1.0.0 \
    httpx==0.27.2 \
    httpcore==1.0.5 \
    anyio==4.3.0 \
    sniffio==1.3.1 \
    greenlet==3.0.3 \
    supabase==2.15.0

COPY packages/k6_worker/ ./packages/k6_worker/
COPY db/ ./db/

ENV PYTHONPATH=/app

CMD ["python3", "-m", "packages.k6_worker.main"]