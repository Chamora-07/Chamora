# AI Performance RCA Engine — Backend API

FastAPI backend that accepts ML anomaly records and returns structured root cause analysis.

## Quick start

```bash
cd rca_engine
pip install -r requirements.txt

cp .env.example .env
# Edit .env — paste your GEMINI_API_KEY (or leave blank for synthetic mode)

uvicorn app.main:app --reload --port 8000
```

Interactive docs: http://localhost:8000/docs

---

## Architecture

```
POST /api/v1/analyze
        │
        ▼
  EvidenceMetrics   ← parses JSON evidence string from ML record
        │
        ▼
  MetricsAnalyzer   ← threshold checks → anomaly list + severity scores
        │               ↓ correlate()
        │           CorrelationMap  (memory / cpu / io / infra / app)
        │
        ▼
  GeminiAnalyzer    ← structured prompt → Gemini 2.5 Flash-Lite
    (if available)     ↓ SRE guardrails validate LLM output
        │              ↓ falls back to SyntheticAnalyzer on failure
        ▼
  RCAResult         ← root_cause, confidence, evidence, reasoning,
                       recommended_actions, metrics_summary, correlations
```

---

## API reference

### `POST /api/v1/analyze`

Analyze a single ML output record.

**Request**
```json
{
  "record": {
    "id": "00112ba4-3c37-4dde-b7dd-65e134b899e2",
    "application_id": 1,
    "config_id": 1,
    "window_timestamp": "2026-04-23 18:24:08",
    "severity": "WARNING",
    "root_cause": "GENERAL_DEGRADATION",
    "evidence": "{\"error_rate\":0,\"has_restart\":true,\"latency_p95\":0.011,\"latency_std\":0.0001,\"disk_io_rate\":0.0009,\"memory_usage\":51530410,\"restart_flag\":0.333,\"cpu_usage_rate\":0.006,\"failure_streak\":0,\"net_throughput\":233.1,\"memory_pressure\":0.127,\"memory_growth_rate\":-991267,\"cpu_container_vs_node_ratio\":0.056}"
  }
}
```

`evidence` can be a JSON string **or** an already-parsed object.

**Response**
```json
{
  "id": "00112ba4-...",
  "application_id": 1,
  "config_id": 1,
  "window_timestamp": "2026-04-23 18:24:08",
  "ml_severity": "WARNING",
  "ml_root_cause": "GENERAL_DEGRADATION",
  "root_cause": "CONFIGURATION_ISSUE",
  "confidence": 0.65,
  "affected_component": "SCHEDULER",
  "evidence": "Restart flag 33%, failure streak 0 — low resource usage rules out OOM.",
  "reasoning": "Repeated restarts without resource pressure suggests misconfigured liveness probes...",
  "recommended_actions": [
    "Review liveness probe thresholds and initial delay settings",
    "Check pod events for OOMKilled vs CrashLoopBackOff distinction",
    "Validate ConfigMap / Secret mounts that may block startup"
  ],
  "anomalies_detected": ["container_restart"],
  "correlations": {
    "memory_issue": false,
    "cpu_issue": false,
    "io_issue": false,
    "infrastructure_issue": true,
    "application_issue": false
  },
  "metrics_summary": {
    "cpu_usage_pct": 0.66,
    "memory_usage_gb": 0.052,
    "memory_pressure_pct": 12.74,
    "memory_growth_mbps": -0.99,
    "latency_p95_ms": 11.85,
    "error_rate_pct": 0.0,
    "disk_io_pct": 0.1,
    "net_throughput_mbps": 233.18,
    "failure_streak": 0
  },
  "analysis_source": "llm",
  "created_at": "2026-05-24T10:00:00Z"
}
```

---

### `POST /api/v1/analyze/batch`

Analyze up to 500 records in one call.

**Request**
```json
{
  "records": [
    { ...record1... },
    { ...record2... }
  ]
}
```

**Response**
```json
{
  "total": 2,
  "results": [ ...RCAResult... ],
  "summary": {
    "total": 2,
    "root_cause_distribution": { "CONFIGURATION_ISSUE": 1, "MEMORY_LEAK": 1 },
    "component_distribution": { "SCHEDULER": 1, "APPLICATION": 1 },
    "analysis_source_distribution": { "llm": 2 },
    "confidence": { "mean": 0.75, "min": 0.65, "max": 0.85, "stdev": 0.14 }
  }
}
```

---

### `GET /api/v1/health`

```json
{ "status": "ok", "llm_provider": "gemini", "use_llm": true, "guardrails_enabled": true }
```

---

## Root cause categories

| Value | Description |
|---|---|
| `MEMORY_LEAK` | Unbounded memory growth (>100 MB/s) |
| `GC_PRESSURE` | High memory pressure causing GC thrashing |
| `CPU_SATURATION` | CPU at/above capacity |
| `RESOURCE_CONTENTION` | Container monopolising node CPU |
| `IO_BOTTLENECK` | Disk throughput saturated |
| `CONFIGURATION_ISSUE` | Probes / orchestration misconfiguration |
| `APPLICATION_BUG` | Elevated errors/latency, no infra cause |
| `NETWORK_BOTTLENECK` | Network throughput limited |
| `UNKNOWN` | No dominant pattern |

## Affected component categories

`APPLICATION` · `SCHEDULER` · `STORAGE` · `DATABASE` · `CACHE` · `NETWORK` · `API_SERVER` · `MESSAGE_QUEUE`

---

## Configuration

All settings are read from `.env` (or environment variables):

| Variable | Default | Description |
|---|---|---|
| `GEMINI_API_KEY` | _(blank)_ | Gemini API key — leave blank for synthetic mode |
| `USE_LLM` | `true` | Enable LLM analysis |
| `GUARDRAILS_ENABLED` | `true` | SRE guardrails that override bad LLM outputs |
| `GEMINI_RPM_DELAY` | `6.0` | Seconds between batch calls (free tier rate limit) |
| `THRESHOLD_LATENCY_P95` | `0.05` | 50 ms |
| `THRESHOLD_ERROR_RATE` | `0.01` | 1 % |
| `THRESHOLD_CPU_USAGE` | `0.85` | 85 % |
| `THRESHOLD_MEMORY_BYTES` | `900000000` | 900 MB |
| `THRESHOLD_MEMORY_PRESSURE` | `0.80` | 80 % |
| `THRESHOLD_MEMORY_GROWTH` | `50000000` | 50 MB/s |
| `THRESHOLD_DISK_IO` | `0.80` | 80 % |
| `THRESHOLD_CPU_NODE_RATIO` | `0.90` | 90 % |
| `THRESHOLD_FAILURE_STREAK` | `5` | consecutive failures |

---

## Integrating with your application

```python
import httpx

async def get_root_cause(ml_record: dict) -> dict:
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "http://localhost:8000/api/v1/analyze",
            json={"record": ml_record},
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()
```

Wire `get_root_cause()` to your "Root Cause" button handler — pass the anomaly record
from your ML model output and display `root_cause`, `confidence`, `evidence`,
and `recommended_actions` from the response.
