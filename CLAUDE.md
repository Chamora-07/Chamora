# CLAUDE.md

> **Single source of truth: [AGENTS.md](AGENTS.md).** Read it first — it covers architecture, data flow, repo layout, env vars, gotchas, and coding conventions.

This file only adds Claude-Code-specific notes that don't belong in AGENTS.md.

## Quick mental model

Chamora is a **streaming anomaly-detection pipeline** keyed by `application_id` end-to-end:

```
VictoriaMetrics → metrics_retriever → raw_metrics
              → feature_builder    → processed_features
              → rule_engine        → anomalies table
              → recommendation-module (LLM chatbot)
```

The FastAPI backend ([main.py](main.py)) **embeds the retriever in-process** via the lifespan handler — so changing retriever code affects the backend container too.

## Where to look first

| Task | Start here |
|---|---|
| Add an API endpoint | [api/v1/api_router.py](api/v1/api_router.py) → relevant `services/*/router.py` |
| Change a metric / PromQL query | [packages/metrics_retriever/metrics_retriever/scraper.py:114](packages/metrics_retriever/metrics_retriever/scraper.py#L114) |
| Add an engineered feature | [packages/feature_builder/feature_builder/transformer.py:86](packages/feature_builder/feature_builder/transformer.py#L86) |
| Tune anomaly scoring | [packages/rule_engine/rule_engine/judge.py:147](packages/rule_engine/rule_engine/judge.py#L147) (`_apply_layered_scoring`) |
| Add a DB column | [db/models.py](db/models.py) — note: no Alembic, schema is applied to Supabase manually |
| Chatbot intent routing | [packages/recommendation-module/backend/app/services/chatbot_service.py:17](packages/recommendation-module/backend/app/services/chatbot_service.py#L17) (`detect_question_type`) |

## Things to avoid

- **Don't run `docker compose down -v`** unless explicitly asked — wipes Kafka offsets and forces all consumers to replay.
- **Don't add a third scraper.** `backend` and `metrics_retriever` services already run the same retriever code; consolidate before adding more.
- **Don't change the Kafka message key** — it must remain `str(application_id)` or the rule engine's per-app windows will scramble.
- **Don't bypass `get_current_user` ownership checks** on resources tied to an `Application`. The canonical pattern is a JOIN through `Application.user_id` (see [services/anomaly_config_registration/service.py:9](services/anomaly_config_registration/service.py#L9)).

## Useful one-liners

```bash
docker compose logs -f rule_engine             # follow anomaly verdicts
docker compose logs -f feature_builder          # follow feature extraction
docker compose restart backend                  # reload backend only (volumes are bind-mounted)
docker compose exec backend uv run python -c "from db.models import *; print(Anomaly.__table__)"
```

Bind mounts mean Python edits don't require a rebuild — `restart` is enough.
