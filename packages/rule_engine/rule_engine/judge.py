from collections import deque
from statistics import mean
import logging

logger = logging.getLogger(__name__)

class SlidingWindowJudge:
    def __init__(self):
        # Buffer keyed by config_id — guarantees one window per endpoint config
        # {config_id: deque([T1, T2, T3], maxlen=3)}
        self.buffers = {}

    def evaluate(self, config_id: int, new_data: dict, cfg: object):
        """
        Processes incoming features, maintains a 3-point window per config,
        and calculates an anomaly score.
        """
        if config_id not in self.buffers:
            self.buffers[config_id] = deque(maxlen=3)
        
        self.buffers[config_id].append(new_data)
        
        app_id = new_data.get("application_id")
        logger.info(
            f"📥 Judge received data for Config {config_id} "
            f"(App {app_id}). Window: {len(self.buffers[config_id])}/3"
        )

        if len(self.buffers[config_id]) < 3:
            return None

        window = list(self.buffers[config_id])
        t1_f, t2_f, t3_f = [w.get('features', {}) for w in window]
        
        mu = {}
        feature_keys = [
            'latency_p95', 'latency_std', 'error_rate', 
            'cpu_usage_rate', 'memory_usage', 'net_throughput',
            'disk_io_rate', 'memory_growth_rate', 'restart_flag',
            'memory_pressure', 'cpu_container_vs_node_ratio', 'failure_streak'
        ]

        for k in feature_keys:
            points = [t.get(k) for t in [t1_f, t2_f, t3_f]]
            valid_points = [v for v in points if isinstance(v, (int, float))]
            mu[k] = mean(valid_points) if valid_points else 0.0

        mu['has_restart'] = any(t.get('restart_flag') == 1 for t in [t1_f, t2_f, t3_f])

        return self._apply_layered_scoring(config_id, mu, window, cfg)

    def _apply_layered_scoring(self, config_id, mu, window, cfg):
        target = window[1]
        t1_f, t2_f, t3_f = [w.get('features', {}) for w in window]
        
        # --- LAYER A: ENDPOINT (50%) ---
        l_e = 0.0
        if mu.get('latency_p95', 0) > cfg.latency_threshold: l_e = 1.0
        if mu.get('error_rate', 0) > cfg.error_rate_threshold: l_e = 1.0
        if mu.get('failure_streak', 0) >= cfg.failure_streak_limit: l_e = 1.0
        if mu.get('latency_std', 0) > 0.5: l_e = max(l_e, 0.7)

        # --- LAYER B: CONTAINER (30%) ---
        l_c = 0.0
        if mu.get('cpu_usage_rate', 0) > cfg.cpu_usage_threshold: l_c = 1.0
        if mu.get('has_restart'): l_c = 1.0

        # Memory Trend: only flag if growth is more than 5% across window
        t1_mem = t1_f.get('memory_usage', 0)
        t3_mem = t3_f.get('memory_usage', 0)
        if t1_mem > 0 and t3_mem > t1_mem:
            growth_pct = (t3_mem - t1_mem) / t1_mem
            if growth_pct > 0.05:
                l_c = max(l_c, 0.4)

        # --- LAYER C: HOST (20%) ---
        l_h = 0.0
        if mu.get('memory_pressure', 0) > cfg.memory_pressure_threshold: l_h = 1.0
        if mu.get('disk_io_rate', 0) > cfg.disk_io_threshold: l_h = 1.0
        if mu.get('cpu_container_vs_node_ratio', 0) > cfg.cpu_node_ratio_threshold: l_h = 1.0

        # --- FINAL SCORE ---
        score = (l_e * 0.5) + (l_c * 0.3) + (l_h * 0.2)
        cause = "GENERAL_DEGRADATION"

        # Specialized Correlation: CPU pressure causing Latency
        if (mu.get('cpu_usage_rate', 0) > (cfg.cpu_usage_threshold * 0.9) and
                mu.get('latency_p95', 0) > cfg.latency_threshold):
            score = min(1.0, score + 0.4)
            cause = "CPU_INDUCED_LATENCY"

        # IO contention correlation
        if mu.get('disk_io_rate', 0) > cfg.disk_io_threshold and mu.get('latency_std', 0) > 0.4:
            score = min(1.0, score + 0.3)
            cause = "IO_WAIT_CONTENTION"

        logger.info(
            f"🔍 DEBUG | Config {config_id} | Score: {score:.2f} | "
            f"Latency: {mu.get('latency_p95', 0):.4f} | "
            f"CPU: {mu.get('cpu_usage_rate', 0):.4f}"
        )

        # ✅ Correct threshold — filters out normal states
        if score < 0.6:
            return None

        logger.warning(
            f"⚖️ Verdict | Config {config_id} | Score: {score:.2f} | "
            f"Severity: {'CRITICAL' if score >= 0.7 else 'WARNING'}"
        )

        return {
            "application_id": target["application_id"],
            "config_id": target["config_id"],
            "endpoint_id": target["endpoint_id"],        # ← pass through for logging
            "timestamp": target["timestamp"],
            "score": round(score, 2),
            "severity": "CRITICAL" if score >= 0.7 else "WARNING",
            "root_cause": cause,
            "evidence": mu
        }