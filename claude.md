# Chamora Backend — CLAUDE.md

## Project Overview

Chamora is a real-time performance anomaly detection platform. The backend is a Python microservices system that ingests live metrics from VictoriaMetrics, engineers features through a stateful transformer, runs a sliding-window anomaly detection engine, and exposes REST APIs for user/application management and an LLM-powered recommendation chatbot. All services are containerized with Docker Compose and communicate through a shared bridge network named `anomaly_detection`.

---

## Repository Structure

```
Chamora-backend/
├── main.py                        # FastAPI entry point (main backend service)
├── pyproject.toml                 # Workspace root — declares packages/* as members
├── uv.lock                        # Locked dependency graph (do not edit manually)
├── docker-compose.yml             # Orchestrates all 7 services
├── Dockerfile                     # Main backend container
├── .env                           # All shared environment variables (not committed)
├── api/
│   └── v1/
│       └── api_router.py          # Mounts all route groups under /api/v1
├── db/
│   ├── base.py                    # SQLAlchemy declarative base
│   ├── connection.py              # Async engine + session factory (asyncpg)
│   ├── init_db.py                 # Table creation on startup
│   ├── models.py                  # All ORM models (see Database Models section)
│   └── storage.py                 # Supabase Storage helpers
├── services/                      # Business logic layer (auth, app, endpoint, etc.)
├── packages/
│   ├── metrics_retriever/         # FastAPI service: scrapes VictoriaMetrics → Kafka
│   ├── feature_builder/           # Kafka worker: raw metrics → 12 engineered features
│   ├── rule_engine/               # Kafka worker: sliding-window anomaly detection → DB
│   ├── recommendation-module/     # FastAPI service: LLM chatbot + RAG knowledge base
│   └── test_cycle_comparison/     # Utility package
```

---

## Tech Stack

### Language & Runtime
- **Python 3.12** (primary), 3.11 supported in some packages
- **uv** (Astral Sh) — workspace-based monorepo package manager and resolver; all installs use `uv sync --frozen`
- **Hatchling** — build backend for all packages

### Web Framework
- **FastAPI** >= 0.115.0 (main backend), >= 0.135.3 (metrics_retriever), version-flexible (recommendation-module)
- **Uvicorn** >= 0.30.0 (main), >= 0.44.0 (metrics_retriever) — ASGI server, hot-reload enabled in recommendation-module
- CORS configured for localhost origins 3000, 4173, 5173, 5174; also accepts regex `https?://(localhost|127\.0\.0\.1)(:\d+)?$`

### Database & ORM
- **Supabase** (hosted PostgreSQL, AWS ap-northeast-1 / Tokyo) >= 2.28.3
- **SQLAlchemy** >= 2.0.49 with fully typed `Mapped` columns; uses PostgreSQL-specific JSONB and UUID dialects
- **asyncpg** >= 0.31.0 — async driver used by the main backend and rule_engine
- **psycopg2-binary** >= 2.9.9 — synchronous fallback driver in rule_engine
- **Supabase Storage** — stores test script files and document uploads (bucket: `test_scripts`)

### Message Streaming
- **Apache Kafka** 7.5.0 (`confluentinc/cp-kafka:7.5.0`) coordinated by **Zookeeper** 7.5.0
- **confluent-kafka** >= 2.4.0 (feature_builder, rule_engine), >= 2.14.0 (metrics_retriever)
- **Kafka UI** (`provectuslabs/kafka-ui:latest`) exposed on port 8085
- Internal broker address: `kafka:29092`; external: `localhost:9092`

### Authentication & Security
- **PyJWT** >= 2.12.1, algorithm HS256, access tokens expire after 60 minutes
- **Passlib** >= 1.7.4 with bcrypt backend; **bcrypt** < 4.0 (pinned to 3.2.2 in lock)
- Secret key via env var `JWT_SECRET_KEY`

### Data Validation & Configuration
- **Pydantic** >= 2.12.5 with email validation and strict typing throughout
- **pydantic-settings** >= 2.2.1 (feature_builder), >= 2.13.1 (metrics_retriever) — loads config from `.env`
- **python-dotenv** >= 1.2.2 — `.env` loading in main backend and rule_engine
- **python-multipart** >= 0.0.26 — multipart file upload support

### HTTP Clients
- **httpx** >= 0.28.1 — async HTTP client used by metrics_retriever to query VictoriaMetrics
- **requests** — synchronous HTTP client in recommendation-module (GitHub API calls)

### AI / LLM / RAG (Recommendation Module)
- **Groq SDK** — LLM inference; model `llama-3.3-70b-versatile` via `GROQ_API_KEY`
- **sentence-transformers** — embedding generation for semantic similarity
- **ChromaDB** — persistent vector store at `RAG_STORE_DIR`
- **vecs** — Supabase vector extension wrapper
- **PyPDF** — PDF text extraction for knowledge base ingestion
- **docker** (Docker SDK) — container introspection from within the recommendation-module

### Metrics & Monitoring
- **VictoriaMetrics** — external time-series database scraped at 1-second intervals; endpoint: `http://16.16.70.92:8428/api/v1/query`
- **Grafana** URLs are stored per Application record in the database (not self-hosted in this stack)

### Containerization
- All containers use `python:3.12-slim` (or `3.11-slim` for recommendation-module)
- Docker Compose manages startup order via `depends_on`; all services on `anomaly_detection` bridge network
- `.venv` cached as a Docker volume (`/app/.venv`) to avoid reinstalling on every code change
- Source code is volume-mounted from the host (`.:/app`) for development live-reload

---

## Service Inventory

| Container | Port (host) | Role | Entry Point |
|---|---|---|---|
| `chamora_backend` | 8000 | Main REST API (auth, apps, endpoints, test scripts) | `uvicorn main:app` |
| `metrics_retriever` | — | Scrapes VictoriaMetrics, publishes to Kafka | FastAPI + background scraper |
| `feature_builder` | — | Kafka worker: 14 raw → 12 features | `python -m feature_builder.main` |
| `rule_engine` | — | Kafka worker: anomaly scoring, writes to DB | `python -m rule_engine.main` |
| `recommendation-module` | 8010 | LLM chatbot + RAG knowledge base | `uvicorn app:app --reload` |
| `kafka` | 9092 | Message broker | Confluent image |
| `kafka_ui` | 8085 | Kafka web UI | Provectus image |
| `zookeeper` | — | Kafka coordination | Confluent image |

---

## Kafka Data Pipeline

```
VictoriaMetrics (external, port 8428)
        ↓  (scraped every 1 second via httpx)
metrics_retriever
        ↓  topic: "raw_metrics"  (key = config_id)
Kafka
        ↓
feature_builder  — stateful transformer, per-config isolated state
        ↓  topic: "processed_features"  (key = config_id)
Kafka
        ↓
rule_engine  — 3-point sliding window judge
        ↓  writes WARNING / CRITICAL anomaly records
Supabase (anomalies table)
```

`config_id` is used as the Kafka partition key at every stage. This guarantees message ordering per endpoint configuration and allows the stateful feature_builder to maintain correct per-config state even when scaled horizontally.

### Kafka Topics
- `raw_metrics` — 14 raw metric values per message (latency percentiles, CPU, memory, network, disk, probe results)
- `processed_features` — 12 engineered features per message (7 direct + 5 computed/stateful)

### The 12 Engineered Features (feature_builder output)
Direct: `latency_p95`, `latency_std`, `error_rate`, `cpu_usage_rate`, `memory_usage`, `net_throughput`, `disk_io_rate`
Computed: `memory_growth_rate` (delta-time), `restart_flag` (start_time comparison), `memory_pressure` (memory/node_memory), `cpu_container_vs_node_ratio`
Stateful: `failure_streak` (cumulative probe failure count, resets per config)

---

## Database Models (db/models.py)

All models use SQLAlchemy's `Mapped` + `mapped_column` typed API with `Base` from `db/base.py`.

- **User** — `id`, `username`, `email`, `hashed_password`; owns Applications
- **Application** — `id`, `user_id (FK)`, `name`, `description`, `github_repo`, `grafana_url`, `victoria_metrics_url`; owns Endpoints, Documents, TestScripts
- **Endpoint** — `id`, `application_id (FK CASCADE)`, `target_name`, `container_name`; has one AnomalyDetectionConfig
- **Document** — `id`, `application_id (FK)`, `file_name`, `storage_path` (Supabase path)
- **TestScript** — `id`, `application_id (FK)`, `script_name`, `storage_path`; has many TestRuns
- **TestRun** — `id`, `test_script_id (FK)`, `status`, `start_time`, `end_time`, `result_file_path`
- **AnomalyDetectionConfig** — `id`, `endpoint_id (FK CASCADE, unique)`, threshold fields for each of the 7 rule signals, `is_active` bool, `ml_inference_enabled` bool, `created_at`
- **Anomaly** — `id (UUID, gen_random_uuid())`, `application_id (FK CASCADE, indexed)`, `config_id (FK CASCADE)`, `window_timestamp`, `score`, `severity` (`WARNING`/`CRITICAL`), `root_cause`, `evidence (JSONB with 12 window-averaged features)`, `created_at`

---

## API Structure

Base prefix: `/api/v1`

Route groups mounted in `api/v1/api_router.py`:
- `auth/` — registration, login, JWT token issue
- `app_registration/` — CRUD for Application records
- `anomaly_config_registration/` — create/update AnomalyDetectionConfig per endpoint
- `document_registration/` — upload/list/delete Documents via Supabase Storage
- `test_script_registration/` — upload/run/list TestScripts, trigger TestRuns

Additional router mounted at root (no `/api/v1` prefix):
- `metrics_retriever.router` — internal endpoints for controlling the scraper manager

Root health endpoint `GET /` returns platform status, engine state, and active endpoint count.

---

## Environment Variables

All defined in `.env` at the repo root. Required variables:

```
# Kafka
KAFKA_BOOTSTRAP_SERVERS=kafka:29092
KAFKA_TOPIC=raw_metrics
KAFKA_TOPIC_FEATURES=processed_features
KAFKA_CONSUMER_GROUP=chamora-rule-engine-v1
SCRAPING_INTERVAL=1.0

# Database
DATABASE_URL=postgresql+asyncpg://<user>:<pass>@<host>/<db>
SUPABASE_URL=https://<project>.supabase.co
SUPABASE_KEY=<service_role_key>
SUPABASE_PUBLISHABLE_KEY=<anon_key>
SUPABASE_STORAGE_TEST_SCRIPTS_BUCKET=test_scripts

# Auth
JWT_SECRET_KEY=<secret>
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60

# Monitoring
VM_URL=http://16.16.70.92:8428/api/v1/query

# AI
GROQ_API_KEY=<key>
GROQ_MODEL=llama-3.3-70b-versatile

# CORS
FRONTEND_ORIGINS=http://localhost:3000,http://localhost:5173,http://localhost:5174,http://localhost:4173
```

The recommendation-module also reads from its own `.env` at `packages/recommendation-module/backend/.env` (GITHUB_TOKEN, RAG_STORE_DIR, etc.).

---

## Common Commands

```bash
# Start the full stack
docker compose up --build

# Start only infrastructure (Kafka + Zookeeper)
docker compose up zookeeper kafka kafka_ui

# Run main backend locally (outside Docker)
uv run uvicorn main:app --reload --port 8000

# Run a worker locally
uv run python -m feature_builder.main
uv run python -m rule_engine.main

# Add a dependency to a specific package
uv add <package> --package feature_builder

# Sync all workspace dependencies
uv sync
```

---

## Key Architectural Decisions

- **`config_id` as Kafka partition key** — maintained consistently across all three pipeline stages to guarantee per-endpoint message ordering without a distributed lock.
- **In-memory state in feature_builder** — `FeatureTransformer` keeps a dict keyed by `config_id`; no DB or Redis dependency. State is lost on restart, which is acceptable because the computed features (growth rate, restart flag, streak) self-correct within a few ticks.
- **No direct DB access in feature_builder** — only rule_engine writes to the database; feature_builder is a pure stream processor.
- **Anomaly UUID primary key** — the `anomalies` table uses `gen_random_uuid()` as PK to avoid integer ID exhaustion under high-frequency anomaly logging.
- **uv workspace** — all packages share a single `uv.lock`; each package's `pyproject.toml` declares only its own dependencies, while the workspace root declares shared runtime dependencies.
- **Supabase Storage for files** — test scripts and documents are stored in Supabase Storage buckets, not on the local filesystem, so they survive container restarts.
