# Production Integration Guide
## AI Performance Intelligent Engine - LLM Component

### Overview

This guide covers how to integrate the LLM-based root cause analysis component into your production AI Performance Intelligent Engine pipeline.

### System Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                     YOUR PLATFORM                            │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  Monitoring System         Rule-Based Engine    ML Model    │
│  (Prometheus/Datadog)  →   (Your Component) →  (Your Model) │
│                                                              │
│                                ↓                             │
│                                                              │
│                    ┌─────────────────────────┐              │
│                    │   LLM Analysis Engine   │  ← THIS      │
│                    │   (Qwen 4B Instruct)    │  COMPONENT  │
│                    │                         │              │
│                    │ • Root Cause Analysis   │              │
│                    │ • Confidence Scoring    │              │
│                    │ • Evidence Generation   │              │
│                    │ • Component Mapping     │              │
│                    └─────────────────────────┘              │
│                                ↓                             │
│                    ┌─────────────────────────┐              │
│                    │    Data Persistence     │              │
│                    │ (PostgreSQL/MongoDB)    │              │
│                    └─────────────────────────┘              │
│                                ↓                             │
│         ┌─────────────────────┴────────────────────┐        │
│         ↓                                           ↓        │
│    Dashboards              Real-time Alerts      Historical │
│    (Grafana/BI)           (PagerDuty/Slack)      Analytics  │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### Integration Points

#### 1. As a Microservice (Recommended)

**Docker Container**:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy application code
COPY ai_performance_llm_engine.py /app/
COPY requirements.txt /app/

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Start API server
CMD ["python", "-m", "uvicorn", "llm_api_server:app", "--host", "0.0.0.0", "--port", "8000"]
```

**requirements.txt**:

```
pandas==2.1.0
numpy==1.24.0
requests==2.31.0
uvicorn==0.23.0
fastapi==0.103.0
pydantic==2.0.0
```

**API Server (llm_api_server.py)**:

```python
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Dict, Any
import json
from ai_performance_llm_engine import AIPerformanceAnalysisEngine

app = FastAPI(
    title="AI Performance LLM Analysis Engine",
    version="1.0.0",
    description="Microservice for root cause analysis"
)

engine = AIPerformanceAnalysisEngine(use_llm=True)

class MLOutputRecord(BaseModel):
    id: str
    application_id: int
    config_id: int
    window_timestamp: str
    severity: str
    root_cause: str
    evidence: str
    created_at: str

class AnalysisResponse(BaseModel):
    root_cause: str
    confidence: float
    evidence: str
    affected_component: str
    analysis_reasoning: str

@app.post("/analyze", response_model=AnalysisResponse)
async def analyze_record(record: MLOutputRecord):
    """Analyze a single ML model output record"""
    try:
        result = engine.process_ml_output(record.dict())
        return AnalysisResponse(
            root_cause=result.root_cause,
            confidence=result.confidence,
            evidence=result.evidence,
            affected_component=result.affected_component,
            analysis_reasoning=result.analysis_reasoning
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/analyze-batch")
async def analyze_batch(records: list[MLOutputRecord]):
    """Analyze multiple records"""
    results = []
    for record in records:
        try:
            result = engine.process_ml_output(record.dict())
            results.append({
                "id": result.id,
                "root_cause": result.root_cause,
                "confidence": result.confidence,
                "affected_component": result.affected_component
            })
        except Exception as e:
            results.append({
                "id": record.id,
                "error": str(e)
            })
    return results

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "llm_available": engine.llm_analyzer.available if engine.llm_analyzer else False
    }

@app.get("/stats")
async def get_stats():
    """Get analysis statistics"""
    return engine.get_summary_stats()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

**Kubernetes Deployment**:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: llm-analysis-engine
  labels:
    app: llm-analysis

spec:
  replicas: 3
  selector:
    matchLabels:
      app: llm-analysis
  
  template:
    metadata:
      labels:
        app: llm-analysis
    spec:
      containers:
      - name: llm-engine
        image: your-registry/llm-analysis-engine:1.0.0
        ports:
        - containerPort: 8000
          name: api
        
        resources:
          requests:
            memory: "2Gi"
            cpu: "1"
          limits:
            memory: "4Gi"
            cpu: "2"
        
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        
        readinessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 10
          periodSeconds: 5

---
apiVersion: v1
kind: Service
metadata:
  name: llm-analysis-engine
spec:
  selector:
    app: llm-analysis
  ports:
  - protocol: TCP
    port: 8000
    targetPort: 8000
  type: ClusterIP
```

**Docker Compose** (for local testing):

```yaml
version: '3.8'

services:
  llm-engine:
    build: .
    ports:
      - "8000:8000"
    environment:
      - PYTHONUNBUFFERED=1
    depends_on:
      - ollama
  
  ollama:
    image: ollama/ollama:latest
    ports:
      - "11434:11434"
    volumes:
      - ollama-data:/root/.ollama
    command: serve

  postgres:
    image: postgres:15
    environment:
      POSTGRES_DB: performance_db
      POSTGRES_USER: analyzer
      POSTGRES_PASSWORD: secure_password
    ports:
      - "5432:5432"
    volumes:
      - postgres-data:/var/lib/postgresql/data

volumes:
  ollama-data:
  postgres-data:
```

#### 2. Direct Integration (Library Usage)

**In Your Application**:

```python
# your_pipeline.py
import pandas as pd
from kafka import KafkaConsumer
from ai_performance_llm_engine import AIPerformanceAnalysisEngine
from database import DatabaseConnection

# Initialize
engine = AIPerformanceAnalysisEngine(use_llm=True)
db = DatabaseConnection('postgresql://user:pass@localhost/db')
kafka_consumer = KafkaConsumer('ml-model-output', bootstrap_servers=['localhost:9092'])

# Main loop
for message in kafka_consumer:
    ml_output = json.loads(message.value)
    
    # Analyze
    analysis = engine.process_ml_output(ml_output)
    
    # Store
    db.insert('llm_analysis_results', {
        'id': analysis.id,
        'root_cause': analysis.root_cause,
        'confidence': analysis.confidence,
        'affected_component': analysis.affected_component,
        'evidence': analysis.evidence,
        'analysis_reasoning': analysis.analysis_reasoning,
        'created_at': analysis.created_at,
    })
    
    # Alert if high confidence
    if analysis.confidence > 0.8:
        send_alert(analysis)
```

### Database Setup

#### PostgreSQL

```bash
# 1. Create database
psql -U postgres -c "CREATE DATABASE performance_engine;"

# 2. Load schema
psql -U postgres -d performance_engine < schema.sql

# 3. Create indexes
psql -U postgres -d performance_engine < indexes.sql

# 4. Create user for application
psql -U postgres -c "CREATE USER analyzer WITH PASSWORD 'secure_password';"
psql -U postgres -c "GRANT ALL PRIVILEGES ON DATABASE performance_engine TO analyzer;"
```

**schema.sql**:

```sql
CREATE TABLE llm_analysis_results (
    id UUID PRIMARY KEY,
    application_id INTEGER NOT NULL,
    config_id INTEGER NOT NULL,
    window_timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    ml_severity VARCHAR(50) NOT NULL,
    ml_root_cause VARCHAR(100) NOT NULL,
    
    root_cause VARCHAR(100) NOT NULL,
    confidence FLOAT NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    affected_component VARCHAR(100) NOT NULL,
    evidence TEXT NOT NULL,
    analysis_reasoning TEXT,
    metrics_summary JSONB,
    
    -- Partitioning by month for large-scale data
    PARTITION BY RANGE (DATE_TRUNC('month', window_timestamp))
);

-- Indexes for common queries
CREATE INDEX idx_confidence_agg ON llm_analysis_results(confidence DESC, window_timestamp DESC);
CREATE INDEX idx_root_cause_agg ON llm_analysis_results(root_cause, window_timestamp DESC);
CREATE INDEX idx_app_time ON llm_analysis_results(application_id, window_timestamp DESC);
```

#### MongoDB

```javascript
db.createCollection("llm_analysis_results", {
  validator: {
    $jsonSchema: {
      bsonType: "object",
      required: ["id", "application_id", "config_id", "root_cause", "confidence"],
      properties: {
        _id: { bsonType: "objectId" },
        id: { bsonType: "string" },
        application_id: { bsonType: "int" },
        config_id: { bsonType: "int" },
        window_timestamp: { bsonType: "date" },
        ml_severity: { bsonType: "string" },
        ml_root_cause: { bsonType: "string" },
        root_cause: { bsonType: "string", enum: [
          "MEMORY_LEAK", "CPU_SATURATION", "NETWORK_BOTTLENECK",
          "APPLICATION_BUG", "RESOURCE_CONTENTION", "GC_PRESSURE",
          "IO_BOTTLENECK", "CONFIGURATION_ISSUE", "UNKNOWN"
        ]},
        confidence: { bsonType: "double", minimum: 0, maximum: 1 },
        affected_component: { bsonType: "string" },
        evidence: { bsonType: "string" },
        analysis_reasoning: { bsonType: "string" },
        metrics_summary: { bsonType: "object" },
        created_at: { bsonType: "date" }
      }
    }
  }
});

// Indexes
db.llm_analysis_results.createIndex({ "application_id": 1, "window_timestamp": -1 });
db.llm_analysis_results.createIndex({ "root_cause": 1 });
db.llm_analysis_results.createIndex({ "confidence": -1 });
db.llm_analysis_results.createIndex({ "window_timestamp": -1 });
```

### Monitoring & Observability

**Prometheus Metrics**:

```python
from prometheus_client import Counter, Histogram, start_http_server
import time

# Metrics
analysis_count = Counter('llm_analysis_total', 'Total analyses')
analysis_latency = Histogram('llm_analysis_latency_seconds', 'Analysis latency')
confidence_histogram = Histogram('llm_confidence_score', 'Confidence score distribution')

# Middleware
def measure_analysis(func):
    def wrapper(*args, **kwargs):
        start = time.time()
        result = func(*args, **kwargs)
        duration = time.time() - start
        
        analysis_count.inc()
        analysis_latency.observe(duration)
        confidence_histogram.observe(result.confidence)
        
        return result
    return wrapper

# Apply to engine
@measure_analysis
def process_ml_output(record):
    return engine.process_ml_output(record)
```

**Logging Configuration**:

```python
import logging
import json

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

# Structured logging
def log_analysis(result):
    logger.info(json.dumps({
        'event': 'analysis_complete',
        'id': result.id,
        'root_cause': result.root_cause,
        'confidence': result.confidence,
        'component': result.affected_component,
        'timestamp': result.created_at
    }))
```

### Performance Optimization

#### 1. Batch Processing Pipeline

```python
from concurrent.futures import ThreadPoolExecutor
import queue

class BatchProcessor:
    def __init__(self, engine, batch_size=100, num_workers=4):
        self.engine = engine
        self.batch_size = batch_size
        self.executor = ThreadPoolExecutor(max_workers=num_workers)
        self.queue = queue.Queue()
    
    def process_batch(self, records):
        results = []
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = [
                executor.submit(self.engine.process_ml_output, record)
                for record in records
            ]
            for future in futures:
                results.append(future.result())
        return results
```

#### 2. Caching

```python
from functools import lru_cache
import hashlib

@lru_cache(maxsize=10000)
def cached_analysis(metric_hash):
    # Cache based on metric fingerprint
    return self.engine.process_ml_output(metric_hash)

def get_metric_hash(metrics):
    # Create consistent hash for metrics
    metric_str = json.dumps(metrics, sort_keys=True)
    return hashlib.md5(metric_str.encode()).hexdigest()
```

#### 3. GPU Acceleration

```bash
# Ollama with GPU support
# For NVIDIA GPUs:
docker run -it --gpus all -v ollama:/root/.ollama ollama/ollama

# For AMD GPUs:
docker run -it --device /dev/kfd --device /dev/dri -v ollama:/root/.ollama ollama/ollama

# For Apple Silicon:
ollama run qwen:4b  # Automatic GPU acceleration
```

### Testing & Validation

```python
# tests/test_llm_engine.py
import unittest
from ai_performance_llm_engine import AIPerformanceAnalysisEngine, MetricsAnalyzer

class TestLLMEngine(unittest.TestCase):
    
    def setUp(self):
        self.engine = AIPerformanceAnalysisEngine(use_llm=False)
    
    def test_metric_parsing(self):
        """Test metric JSON parsing"""
        analyzer = MetricsAnalyzer()
        metrics_json = '{"error_rate": 0.01, "cpu_usage_rate": 0.8, ...}'
        metrics = analyzer.parse_metrics(metrics_json)
        self.assertIsNotNone(metrics)
    
    def test_anomaly_detection(self):
        """Test anomaly detection"""
        # Create mock metrics
        metrics = MetricData(
            cpu_usage_rate=0.9,  # High
            memory_usage=1e10,   # High
            # ... other fields
        )
        anomalies, _ = MetricsAnalyzer.identify_anomalies(metrics)
        self.assertIn('high_cpu_usage', anomalies)
        self.assertIn('high_memory_usage', anomalies)
    
    def test_analysis_output(self):
        """Test analysis output structure"""
        result = self.engine.process_ml_output(sample_record)
        self.assertIsNotNone(result.root_cause)
        self.assertGreaterEqual(result.confidence, 0)
        self.assertLessEqual(result.confidence, 1)
        self.assertIsNotNone(result.affected_component)

if __name__ == '__main__':
    unittest.main()
```

### Troubleshooting Checklist

- [ ] LLM service running: `curl http://localhost:11434/api/tags`
- [ ] Database connected: `psql -U analyzer -d performance_engine`
- [ ] API responding: `curl http://localhost:8000/health`
- [ ] Logs rotating: Check `/var/log/llm-analysis/`
- [ ] Metrics exporting: `curl http://localhost:9090/metrics`
- [ ] Database backups: Automated daily at 02:00 UTC
- [ ] Disk space: > 50% free on data partition
- [ ] Memory usage: < 80% sustained
- [ ] CPU usage: < 70% sustained
- [ ] Network latency to LLM: < 100ms

### Scaling Considerations

| Metric | Single Instance | 3-Node Cluster | 10-Node Cluster |
|--------|-----------------|----------------|-----------------|
| Records/min | 200-500 | 600-1500 | 2000-5000 |
| Latency p95 | 5s | 3s | 2s |
| Memory (GB) | 2-4 | 6-12 | 20-40 |
| CPU Cores | 1-2 | 4-8 | 10-20 |

### Support & Maintenance

- **Log Retention**: 30 days
- **Backup Strategy**: Daily incremental, weekly full
- **Update Cycle**: Monthly security patches, quarterly feature releases
- **SLA Target**: 99.9% availability

---

**Ready for Production?** → Deploy using the Kubernetes manifests above
**Need Help?** → Check README.md for detailed documentation
