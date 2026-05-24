# AGENTS.md

Guidance for any AI coding agent working in this repository. Read this before making changes.

## What this project is

**Chamora** is a multi-tenant, real-time anomaly detection platform for containerised services. The pipeline:

```
VictoriaMetrics → metrics_retriever → Kafka(raw_metrics)
              → feature_builder    → Kafka(processed_features)
              → rule_engine        → Postgres(anomalies)
              → recommendation-module (LLM chatbot + dashboard)
```

Every message is keyed by `application_id` end-to-end to preserve per-app partition ordering — the `rule_engine` relies on this for its 3-point sliding window.

## Repo layout

```
main.py                      FastAPI entrypoint — also starts the retriever in-process via lifespan
api/v1/api_router.py         Mounts /api/v1/{auth,application,test-scripts,anomaly-configs}
services/                    Feature modules (router + service + schemas per feature)
db/                          SQLAlchemy 2.0 async models, connection, Supabase storage helpers
packages/                    uv workspace packages
  metrics_retriever/           Polls each app's VM URL every 1s, produces to raw_metrics
  feature_builder/             Consumes raw_metrics, builds 12 features, produces processed_features
  rule_engine/                 Consumes processed_features, 3-point sliding window, writes anomalies
  recommendation-module/       Separate FastAPI (port 8010) — Groq LLM chatbot + dashboard
docker-compose.yml           8 services: kafka, zookeeper, kafka_ui, backend, metrics_retriever, feature_builder, rule_engine, recommendation-module
```

## Tech stack

- Python 3.12, FastAPI, `uv` workspaces (see root `pyproject.toml`)
- SQLAlchemy 2.0 async (`asyncpg`), Supabase-hosted Postgres
- `confluent-kafka` producer/consumer
- `pydantic-settings` for config
- Groq LLM (`llama-3.3-70b-versatile` default) for the recommendation module

## Running locally

```bash
docker compose up --build              # full stack
docker compose logs -f rule_engine     # follow one service
docker compose ps                       # service status
docker compose down                     # stop (keeps Kafka volume)
docker compose down -v                  # full reset (wipes Kafka state)
```

Service URLs once up:
- Backend API → http://localhost:8000/docs
- Recommendation API → http://localhost:8010/docs
- Kafka UI → http://localhost:8085

## Required environment

Root `.env` (already populated for the maintainer):
- `DATABASE_URL` — Supabase Postgres (with `postgresql://` prefix; connection.py auto-rewrites to `postgresql+asyncpg://`)
- `SUPABASE_URL`, `SUPABASE_KEY`, `SUPABASE_PUBLISHABLE_KEY`, `SUPABASE_STORAGE_TEST_SCRIPTS_BUCKET`
- `KAFKA_BOOTSTRAP_SERVERS`, `KAFKA_TOPIC`, `KAFKA_TOPIC_FEATURES`, `KAFKA_CONSUMER_GROUP`
- `GROQ_API_KEY`, `GROQ_MODEL`
- `JWT_SECRET_KEY`, `ALGORITHM`, `ACCESS_TOKEN_EXPIRE_MINUTES`

`packages/recommendation-module/backend/.env` — required by compose (can be an empty stub; shared keys fall back to root `.env`).

## Gotchas — read before editing

1. **`backend` service needs `VM_URL`** even though it's "just" the API. `main.py` imports `metrics_retriever.router` which instantiates `Settings()` (in [packages/metrics_retriever/metrics_retriever/config.py](packages/metrics_retriever/metrics_retriever/config.py)); that field is required at import time. The fix is already in `docker-compose.yml`.

2. **Backend and `metrics_retriever` services run the same `main.py`.** Both start the `RetrieverManager` and scrape simultaneously — currently a duplicate. Don't add a third scraper without consolidating these first.

3. **Per-app VM URLs live on the `Application` row** (`applications.victoria_metrics_url`). The global `VM_URL` env var is only used by older code paths; the scraper joins through to `Application.victoria_metrics_url` ([packages/metrics_retriever/metrics_retriever/db_manager.py:33](packages/metrics_retriever/metrics_retriever/db_manager.py#L33)).

4. **Rule-engine threshold is currently `0.3`** (testing) — production spec is `0.55`. See [packages/rule_engine/rule_engine/judge.py:188](packages/rule_engine/rule_engine/judge.py#L188). Don't tune scoring without knowing this.

5. **Identity-Aware Kafka keys.** Producers always key by `str(application_id)`. The `rule_engine` keeps a per-`app_id` `deque(maxlen=3)` — losing the key would scramble the windows.

6. **`prepared_statement_cache_size=0` is intentional** on all asyncpg engines — Supabase's PgBouncer breaks SQLAlchemy's default prepared-statement cache.

7. **On-demand refresh.** When users create/update/delete `AnomalyDetectionConfig`, the router calls `retriever_manager.refresh_jobs()` so scraping starts within ~1s instead of waiting for the 60s observer loop. Preserve that call if you touch [services/anomaly_config_registration/router.py](services/anomaly_config_registration/router.py).

## Coding conventions

- **Async everywhere** — FastAPI handlers, SQLAlchemy sessions, httpx calls. Never block.
- **Service layer separation**: `router.py` → thin HTTP wrapper; `service.py` → business logic with `db: AsyncSession`; `schemas.py` → Pydantic models.
- **Auth**: `current_user = Depends(get_current_user)` on protected routes; ownership checks via JOINs through `Application.user_id` (see [services/anomaly_config_registration/service.py:9](services/anomaly_config_registration/service.py#L9) for the canonical pattern).
- **Adding a new Kafka stage**: produce keyed by `application_id`, set `auto.offset.reset='latest'` on consumers (matches `rule_engine` policy), use a distinct `group.id`.

## Database

Models in [db/models.py](db/models.py). Schema is:
`User → Application → Endpoint → AnomalyDetectionConfig` (1:1).
Detected anomalies land in `anomalies` (UUID PK, JSONB `evidence` of the 12 averaged features). All FKs use `ondelete="CASCADE"`.

There are no Alembic migrations — schema is created from `Base.metadata` against Supabase. If you change a model, you'll need to migrate Supabase manually.

## When something breaks

- **`pydantic_core.ValidationError: Field required`** at startup → an env var is missing for that container. Check the `environment:` block in `docker-compose.yml`.
- **`UNKNOWN_TOPIC_OR_PART`** in feature_builder/rule_engine logs at startup → benign, resolves once the upstream producer creates the topic on first message.
- **`Discarding payload ... metrics missing`** → that app's VM URL isn't returning data (host unreachable or no metrics scraped on the VM side). Fix the URL or set `is_active=False` on its config.
