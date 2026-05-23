from app.core.supabase_client import get_supabase_client
def get_current_anomaly_state(app_id):
    return {
        "application_id": app_id,
        "anomaly_detected": True,
        "mode": "diagnostic",
        "severity": "high",
        "summary": "High CPU and response time anomaly detected.",
        "active_since": "2026-04-12 13:00:00",
        "latest_event_id": "evt-001",
        "updated_at": "2026-04-12 14:00:00",
    }


def get_anomaly_event_by_time_window(app_id, question):
    q = question.lower()

    time_window = "yesterday between 1 PM and 2 PM"
    if "yesterday" not in q:
        time_window = "the selected anomaly window"

    return {
        "id": "evt-001",
        "application_id": app_id,
        "start_time": "2026-04-12 13:00:00",
        "end_time": "2026-04-12 14:00:00",
        "status": "resolved",
        "severity": "high",
        "anomaly_type": "combined",
        "summary": f"During {time_window}, CPU usage and response time increased abnormally.",
        "root_cause_hint": "Possible CPU-intensive endpoint activity or inefficient backend processing.",
        "metrics_snapshot_json": {
            "cpu_percent": 91.0,
            "memory_percent": 78.0,
            "avg_response_time_ms": 820.0,
            "throughput_rps": 140.0,
            "error_rate_percent": 4.2
        },
        "triggered_flags_json": [
            {
                "metric": "cpu_percent",
                "value": 91.0,
                "threshold": 80.0,
                "message": "CPU usage exceeded threshold."
            },
            {
                "metric": "avg_response_time_ms",
                "value": 820.0,
                "threshold": 500.0,
                "message": "Average response time exceeded expected range."
            }
        ],
        "recommended_actions_json": [
            "Inspect high-CPU endpoints during the anomaly window.",
            "Check recent deployments or configuration changes.",
            "Review container resource limits and backend processing bottlenecks."
        ],
        "related_test_run_id": None,
        "created_at": "2026-04-12 14:00:00"
    }