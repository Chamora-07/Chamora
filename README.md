# 🛡️ Chamora Backend Services (FastAPI + Kafka + Supabase)

This repository contains the backend components of the Chamora Platform. It handles metric retrieval, ingestion/processing pipelines via Kafka, database management with Supabase, and Root Cause Analysis (RCA) orchestration.

---

## 🏗️ Services Overview

The backend uses Docker Compose to run a multi-service stack:
*   **`zookeeper` & `kafka`**: Ingestion layer for streaming telemetry metrics.
*   **`metrics_retriever`**: Periodically scrapes Prometheus-compatible node metrics.
*   **`feature_builder`**: Accumulates and rolls metrics into analysis feature vectors.
*   **`rule_engine`**: High-performance rule processor that stores detected anomalies to Supabase.
*   **`rca_engine`**: Orchestrates ML early warning checks and integrates Ollama's local LLM.
*   **`recommendation-module`**: Interactive SRE Chatbot assistant interface.
*   **`k6_worker`**: Orchestrates automated API load generation.

---

## 🤖 Custom Qwen-SRE LLM Setup

The LLM component is powered by a locally hosted fine-tuned model (`qwen-sre:latest`) running inside Ollama.

### 1. Host the Model GGUF File
The fine-tuned model weights are saved in GGUF format (`qwen-sre.gguf`, ~3.1 GB). Because GitHub restricts uploads above 100MB, **do not commit the `.gguf` file to this repository.** Instead:
1. Upload the `qwen-sre.gguf` file to your model hub repository on [Hugging Face](https://huggingface.co/).
2. Keep the `Modelfile` in the root of the model repository.

### 2. Import into Ollama Locally
To load the model on any development machine:
1. Install [Ollama](https://ollama.com/).
2. Download your `qwen-sre.gguf` file and place it in the same directory as the `Modelfile`.
3. Run the import command in your terminal:
   ```bash
   ollama create qwen-sre -f Modelfile
   ```
4. Verify the model is registered:
   ```bash
   ollama list
   ```

---

## 🚀 Running the Backend Services

### Prerequisites
*   Docker & Docker Desktop installed.
*   Ollama running locally on the host machine.

### Setup and Launch
1. Copy the `.env` template:
   ```bash
   cp .env.example .env
   ```
2. Configure the following critical environment variables inside `.env`:
   *   `DATABASE_URL`: Connection string to PostgreSQL / Supabase instance.
   *   `OLLAMA_API_URL`: Set to `http://host.docker.internal:11434` so the dockerized backend can talk to the Ollama server on your host machine.
3. Start the entire backend docker stack:
   ```bash
   docker compose up -d --build
   ```
4. Check running status:
   ```bash
   docker compose ps
   ```
5. View service logs:
   ```bash
   docker compose logs -f [service_name]
   ```