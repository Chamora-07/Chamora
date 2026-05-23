from app.core.supabase_client import get_supabase_client
def detect_anomaly(metrics: dict) -> dict:
    cpu = metrics.get("cpu_percent", 0)
    memory = metrics.get("memory_percent", 0)

    flags = []

    if cpu > 80:
        flags.append({
            "type": "cpu",
            "value": cpu,
            "threshold": 80,
            "message": f"CPU usage is high at {cpu}%"
        })

    if memory > 75:
        flags.append({
            "type": "memory",
            "value": memory,
            "threshold": 75,
            "message": f"Memory usage is high at {memory}%"
        })

    if flags:
        return {
            "available": True,
            "status": "risk",
            "flags": flags
        }

    return {
        "available": True,
        "status": "safe",
        "flags": []
    }

def get_anomalies_between(app_id, start_time, end_time, supabase=None):
    """Fetch anomalies for an application between two datetimes.

    start_time and end_time should be datetime objects or strings.
    """
    if supabase is None:
        supabase = get_supabase_client()

    # If datetimes are provided, convert to ISO format strings
    try:
        start_ts = start_time.isoformat()
    except AttributeError:
        start_ts = str(start_time)

    try:
        end_ts = end_time.isoformat()
    except AttributeError:
        end_ts = str(end_time)

    result = (
        supabase.table("anomalies")
        .select("*")
        .eq("application_id", app_id)
        .gte("window_timestamp", start_ts)
        .lte("window_timestamp", end_ts)
        .execute()
    )

    return result.data or []