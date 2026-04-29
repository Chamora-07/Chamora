import logging
import time

logger = logging.getLogger(__name__)

class FeatureTransformer:
    def __init__(self):
        # State store keyed by config_id — guaranteed unique per endpoint config
        # { config_id: { "mem": X, "ts": Y, "start_time": Z, "streak": S } }
        self.state = {}

    def transform(self, data: dict) -> dict:
        app_id = data.get("application_id")
        endpoint_id = data.get("endpoint_id")
        config_id = data.get("config_id")
        raw = data.get("metrics", {})
        now = data.get("timestamp", time.time())

        logger.info(f"⚡ RECEIVED: Processing raw metrics for Config {config_id}")

        def safe_get(key, default=0.0):
            val = raw.get(key)
            return val if isinstance(val, (int, float)) else default

        # ✅ State is isolated per config_id — no cross-contamination between endpoints
        prev = self.state.get(config_id, {})

        # 1. Memory Growth Rate
        m_t = safe_get("container_memory_usage_bytes")
        m_prev = prev.get("mem", m_t)
        dt = max(0.1, now - prev.get("ts", now - 1))
        mem_growth = (m_t - m_prev) / dt

        # 2. Restart Flag
        st_t = safe_get("container_start_time_seconds")
        st_prev = prev.get("start_time", st_t)
        restart = 1 if st_t > st_prev else 0

        # 3. Memory Pressure
        node_avail = safe_get("node_memory_MemAvailable_bytes")
        mem_pressure = m_t / node_avail if node_avail > 0 else 0.0

        # 4. CPU Ratio
        c_cpu = safe_get("cpu_usage_rate")
        n_cpu = safe_get("node_cpu_total")
        cpu_ratio = c_cpu / n_cpu if n_cpu > 0 else 0.0

        # 5. Failure Streak
        success = safe_get("probe_success", default=1.0)
        prev_streak = prev.get("streak", 0)
        current_streak = prev_streak + 1 if success == 0 else 0

        # ✅ Update state under config_id — never None
        self.state[config_id] = {
            "mem": m_t,
            "ts": now,
            "start_time": st_t,
            "streak": current_streak
        }

        processed_payload = {
            "application_id": app_id,
            "config_id": config_id,
            "endpoint_id": endpoint_id,
            "timestamp": now,
            "features": {
                "latency_p95": safe_get("latency_p95"),
                "latency_std": safe_get("latency_std"),
                "error_rate": safe_get("error_rate"),
                "cpu_usage_rate": c_cpu,
                "memory_usage": safe_get("memory_usage_avg"),
                "net_throughput": safe_get("net_throughput"),
                "disk_io_rate": safe_get("disk_io_rate"),
                "memory_growth_rate": mem_growth,
                "restart_flag": restart,
                "memory_pressure": mem_pressure,
                "cpu_container_vs_node_ratio": cpu_ratio,
                "failure_streak": current_streak
            }
        }

        logger.info(f"✅ PROCESSED: 12 features built for config {config_id}")
        return processed_payload