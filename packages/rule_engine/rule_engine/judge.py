# from collections import deque
# from statistics import mean
# import logging

# logger = logging.getLogger(__name__)

# class SlidingWindowJudge:
#     def __init__(self):
#         # Buffer: {app_id: deque([T1, T2, T3], maxlen=3)}
#         self.buffers = {}

#     def evaluate(self, app_id: int, new_data: dict, cfg: object):
#         if app_id not in self.buffers:
#             self.buffers[app_id] = deque(maxlen=3)
        
#         self.buffers[app_id].append(new_data)
#         if len(self.buffers[app_id]) < 3:
#             return None

#         # 1. Align the window
#         window = list(self.buffers[app_id])
#         t1, t2, t3 = [w['features'] for w in window]

#         # 2. Calculate Window Means for robust analysis
#         mu = {k: mean([t1[k], t2[k], t3[k]]) for k in t1.keys() if isinstance(t1[k], (int, float))}
#         # Explicit check for restarts in the window
#         mu['has_restart'] = any(w['features']['restart_flag'] == 1 for w in window)

#         return self._apply_layered_scoring(mu, window, cfg)

#     def _apply_layered_scoring(self, mu, window, cfg):
#         # Middle point (T2) is our target for the record
#         target = window[1]
        
#         # --- LAYER A: ENDPOINT (50%) ---
#         l_e = 0.0
#         if mu['latency_p95'] > cfg.latency_threshold: l_e = 1.0
#         if mu['error_rate'] > cfg.error_rate_threshold: l_e = 1.0
#         if mu['failure_streak'] >= cfg.failure_streak_limit: l_e = 1.0
#         if mu['latency_std'] > 0.5: l_e = max(l_e, 0.7) # Jitter check

#         # --- LAYER B: CONTAINER (30%) ---
#         l_c = 0.0
#         if mu['cpu_usage_rate'] > cfg.cpu_usage_threshold: l_c = 1.0
#         if mu['has_restart']: l_c = 1.0
#         # Memory Trend: If window is consistently rising
#         if window[2]['features']['memory_usage'] > window[0]['features']['memory_usage']:
#             l_c = max(l_c, 0.4)

#         # --- LAYER C: HOST (20%) ---
#         l_h = 0.0
#         if mu['memory_pressure'] > cfg.memory_pressure_threshold: l_h = 1.0
#         if mu['disk_io_rate'] > cfg.disk_io_threshold: l_h = 1.0
#         if mu['cpu_container_vs_node_ratio'] > cfg.cpu_node_ratio_threshold: l_h = 1.0

#         # --- ROBUST CORRELATION SIGNATURES ---
#         score = (l_e * 0.5) + (l_c * 0.3) + (l_h * 0.2)
#         cause = "GENERAL_DEGRADATION"

#         # Logic: CPU bottleneck causing Latency
#         if mu['cpu_usage_rate'] > (cfg.cpu_usage_threshold * 0.9) and mu['latency_p95'] > cfg.latency_threshold:
#             score = min(1.0, score + 0.4)
#             cause = "CPU_INDUCED_LATENCY"

#         # Logic: Resource contention (Host Disk + Network impact)
#         if mu['disk_io_rate'] > cfg.disk_io_threshold and mu['latency_std'] > 0.4:
#             score = min(1.0, score + 0.3)
#             cause = "IO_WAIT_CONTENTION"

#         if score < 0.55: return None # Filter out NORMAL states

#         return {
#             "application_id": target["application_id"],
#             "config_id": target["config_id"],
#             "timestamp": target["timestamp"], # T2
#             "score": round(score, 2),
#             "severity": "CRITICAL" if score >= 0.7 else "WARNING",
#             "root_cause": cause,
#             "evidence": mu
#         } 
# ##############################################

#  


from collections import deque
from statistics import mean
import logging

# Set up logging to ensure we see our debug outputs
logger = logging.getLogger(__name__)

class SlidingWindowJudge:
    def __init__(self):
        # Buffer: {app_id: deque([T1, T2, T3], maxlen=3)}
        self.buffers = {}

    def evaluate(self, app_id: int, new_data: dict, cfg: object):
        """
        Processes incoming features, maintains a 3-point window, 
        and calculates an anomaly score.
        """
        if app_id not in self.buffers:
            self.buffers[app_id] = deque(maxlen=3)
        
        self.buffers[app_id].append(new_data)
        
        # Heartbeat log to prove the Judge is receiving data from Kafka
        logger.info(f"📥 Judge received data for App {app_id}. Window: {len(self.buffers[app_id])}/3")

        if len(self.buffers[app_id]) < 3:
            return None

        # 1. Align the window (T1, T2, T3)
        window = list(self.buffers[app_id])
        
        # 2. Extract feature dictionaries safely
        # Feature Builder sends data as: {"features": {"cpu_usage_rate": 0.5, ...}}
        t1_f, t2_f, t3_f = [w.get('features', {}) for w in window]
        
        # 3. Robust Window Averaging (Handles None and Missing Keys)
        mu = {}
        # These keys must match the FeatureTransformer output exactly
        feature_keys = [
            'latency_p95', 'latency_std', 'error_rate', 
            'cpu_usage_rate', 'memory_usage', 'net_throughput',
            'disk_io_rate', 'memory_growth_rate', 'restart_flag',
            'memory_pressure', 'cpu_container_vs_node_ratio', 'failure_streak'
        ]

        for k in feature_keys:
            # Extract values from all 3 points, filtering out None
            points = [t.get(k) for t in [t1_f, t2_f, t3_f]]
            valid_points = [v for v in points if isinstance(v, (int, float))]
            
            if valid_points:
                mu[k] = mean(valid_points)
            else:
                mu[k] = 0.0 # Default to 0.0 if data is missing

        # Restart Logic: If any packet in the window shows a restart
        mu['has_restart'] = any(t.get('restart_flag') == 1 for t in [t1_f, t2_f, t3_f])

        # Pass app_id so we can trigger the specific debug log
        return self._apply_layered_scoring(app_id, mu, window, cfg)

    def _apply_layered_scoring(self, app_id, mu, window, cfg):
        # Target the middle point (T2) for the anomaly record
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
        
        # Memory Trend: If current memory (T3) is higher than start of window (T1)
        if t3_f.get('memory_usage', 0) > t1_f.get('memory_usage', 0):
            l_c = max(l_c, 0.4)

        # --- LAYER C: HOST (20%) ---
        l_h = 0.0
        if mu.get('memory_pressure', 0) > cfg.memory_pressure_threshold: l_h = 1.0
        if mu.get('disk_io_rate', 0) > cfg.disk_io_threshold: l_h = 1.0
        if mu.get('cpu_container_vs_node_ratio', 0) > cfg.cpu_node_ratio_threshold: l_h = 1.0

        # --- FINAL SCORE CALCULATION ---
        score = (l_e * 0.5) + (l_c * 0.3) + (l_h * 0.2)
        cause = "GENERAL_DEGRADATION"

        # Specialized Correlation: CPU pressure causing Latency
        if mu.get('cpu_usage_rate', 0) > (cfg.cpu_usage_threshold * 0.9) and mu.get('latency_p95', 0) > cfg.latency_threshold:
            score = min(1.0, score + 0.4)
            cause = "CPU_INDUCED_LATENCY"

        # --- TEMPORARY DEBUG LINE ---
        if app_id == 1:
            logger.info(f"🔍 DEBUG | App 1 | Score: {score:.2f} | Latency: {mu.get('latency_p95', 0):.4f} | CPU: {mu.get('cpu_usage_rate', 0):.4f}")

        # Filter out anything below the testing threshold
        if score < 0.6: 
            return None 

        logger.warning(f"⚖️ Verdict Generated | App: {app_id} | Score: {score:.2f} | Severity: {'CRITICAL' if score >= 0.7 else 'WARNING'}")

        return {
            "application_id": target["application_id"],
            "config_id": target["config_id"],
            "timestamp": target["timestamp"],
            "score": round(score, 2),
            "severity": "CRITICAL" if score >= 0.7 else "WARNING",
            "root_cause": cause,
            "evidence": mu
        }