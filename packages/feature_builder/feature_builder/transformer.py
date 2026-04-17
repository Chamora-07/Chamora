import logging
import time

logger = logging.getLogger(__name__)

class FeatureTransformer:
    def __init__(self):
        # State store: { application_id: { "last_val": X, "timestamp": Y, "streak": Z } }
        self.state = {}

    def transform(self, data: dict) -> dict:
        app_id = data["application_id"]
        raw = data["metrics"]
        now = data["timestamp"]
        
        # Get previous state or default to current
        prev = self.state.get(app_id, {})
        
        # 8. Memory Growth Rate: (Mt - Mt-1) / dt
        m_t = raw.get("container_memory_usage_bytes", 0)
        m_prev = prev.get("mem", m_t)
        dt = max(0.1, now - prev.get("ts", now - 1))
        mem_growth = (m_t - m_prev) / dt

        # 9. Restart Flag: 1 if start_time increases
        st_t = raw.get("container_start_time_seconds", 0)
        st_prev = prev.get("start_time", st_t)
        restart = 1 if st_t > st_prev else 0

        # 10. Memory Pressure: Container / Node Available
        node_avail = raw.get("node_memory_MemAvailable_bytes", 1)
        mem_pressure = m_t / node_avail if node_avail > 0 else 0

        # 11. CPU Ratio: Container Rate / Node Total Rate
        c_cpu = raw.get("cpu_usage_rate", 0)
        n_cpu = raw.get("node_cpu_total", 1)
        cpu_ratio = c_cpu / n_cpu if n_cpu > 0 else 0

        # 12. Failure Streak: Incremental counter
        success = raw.get("probe_success", 1)
        prev_streak = prev.get("streak", 0)
        current_streak = prev_streak + 1 if success == 0 else 0

        # Update the state store
        self.state[app_id] = {
            "mem": m_t,
            "ts": now,
            "start_time": st_t,
            "streak": current_streak
        }

        # Build the Final 12-Feature Set
        return {
            "application_id": app_id,
            "config_id": data["config_id"],
            "timestamp": now,
            "features": {
                # Direct from VictoriaMetrics
                "latency_p95": raw.get("latency_p95"),
                "latency_std": raw.get("latency_std"),
                "error_rate": raw.get("error_rate"),
                "cpu_usage_rate": c_cpu,
                "memory_usage": raw.get("memory_usage_avg"),
                "net_throughput": raw.get("net_throughput"),
                "disk_io_rate": raw.get("disk_io_rate"),
                # Engineered
                "memory_growth_rate": mem_growth,
                "restart_flag": restart,
                "memory_pressure": mem_pressure,
                "cpu_container_vs_node_ratio": cpu_ratio,
                "failure_streak": current_streak
            }
        }