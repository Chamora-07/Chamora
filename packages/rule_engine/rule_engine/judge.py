from collections import deque
from statistics import mean
import logging

logger = logging.getLogger(__name__)

class SlidingWindowJudge:
    def __init__(self):
        # Buffer: {app_id: deque([T1, T2, T3], maxlen=3)}
        self.buffers = {}

    def evaluate(self, app_id: int, new_data: dict, cfg: object):
        if app_id not in self.buffers:
            self.buffers[app_id] = deque(maxlen=3)
        
        self.buffers[app_id].append(new_data)
        if len(self.buffers[app_id]) < 3:
            return None

        # 1. Align the window
        window = list(self.buffers[app_id])
        t1, t2, t3 = [w['features'] for w in window]

        # 2. Calculate Window Means for robust analysis
        mu = {k: mean([t1[k], t2[k], t3[k]]) for k in t1.keys() if isinstance(t1[k], (int, float))}
        # Explicit check for restarts in the window
        mu['has_restart'] = any(w['features']['restart_flag'] == 1 for w in window)

        return self._apply_layered_scoring(mu, window, cfg)

    def _apply_layered_scoring(self, mu, window, cfg):
        # Middle point (T2) is our target for the record
        target = window[1]
        
        # --- LAYER A: ENDPOINT (50%) ---
        l_e = 0.0
        if mu['latency_p95'] > cfg.latency_threshold: l_e = 1.0
        if mu['error_rate'] > cfg.error_rate_threshold: l_e = 1.0
        if mu['failure_streak'] >= cfg.failure_streak_limit: l_e = 1.0
        if mu['latency_std'] > 0.5: l_e = max(l_e, 0.7) # Jitter check

        # --- LAYER B: CONTAINER (30%) ---
        l_c = 0.0
        if mu['cpu_usage_rate'] > cfg.cpu_usage_threshold: l_c = 1.0
        if mu['has_restart']: l_c = 1.0
        # Memory Trend: If window is consistently rising
        if window[2]['features']['memory_usage'] > window[0]['features']['memory_usage']:
            l_c = max(l_c, 0.4)

        # --- LAYER C: HOST (20%) ---
        l_h = 0.0
        if mu['memory_pressure'] > cfg.memory_pressure_threshold: l_h = 1.0
        if mu['disk_io_rate'] > cfg.disk_io_threshold: l_h = 1.0
        if mu['cpu_container_vs_node_ratio'] > cfg.cpu_node_ratio_threshold: l_h = 1.0

        # --- ROBUST CORRELATION SIGNATURES ---
        score = (l_e * 0.5) + (l_c * 0.3) + (l_h * 0.2)
        cause = "GENERAL_DEGRADATION"

        # Logic: CPU bottleneck causing Latency
        if mu['cpu_usage_rate'] > (cfg.cpu_usage_threshold * 0.9) and mu['latency_p95'] > cfg.latency_threshold:
            score = min(1.0, score + 0.4)
            cause = "CPU_INDUCED_LATENCY"

        # Logic: Resource contention (Host Disk + Network impact)
        if mu['disk_io_rate'] > cfg.disk_io_threshold and mu['latency_std'] > 0.4:
            score = min(1.0, score + 0.3)
            cause = "IO_WAIT_CONTENTION"

        if score < 0.55: return None # Filter out NORMAL states

        return {
            "application_id": target["application_id"],
            "config_id": target["config_id"],
            "timestamp": target["timestamp"], # T2
            "score": round(score, 2),
            "severity": "CRITICAL" if score >= 0.7 else "WARNING",
            "root_cause": cause,
            "evidence": mu
        }