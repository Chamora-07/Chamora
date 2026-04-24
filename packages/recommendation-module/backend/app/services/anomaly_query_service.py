from datetime import datetime, timedelta, timezone
from app.core.supabase_client import get_supabase_client


def parse_time_window_from_question(question: str) -> tuple[str | None, str | None]:
    q = question.lower()

    if "yesterday" in q and "1 pm" in q and "2 pm" in q:
        now = datetime.now(timezone.utc)
        yesterday = now - timedelta(days=1)
        start = yesterday.replace(hour=13, minute=0, second=0, microsecond=0)
        end = yesterday.replace(hour=14, minute=0, second=0, microsecond=0)
        return start.isoformat(), end.isoformat()

    if "yesterday" in q:
        now = datetime.now(timezone.utc)
        yesterday = now - timedelta(days=1)
        start = yesterday.replace(hour=0, minute=0, second=0, microsecond=0)
        end = yesterday.replace(hour=23, minute=59, second=59, microsecond=999999)
        return start.isoformat(), end.isoformat()

    return None, None


def get_latest_anomaly_for_app(app_id: str) -> dict:
    supabase = get_supabase_client()

    result = (
        supabase.table("anomalies")
        .select("*")
        .eq("application_id", app_id)
        .order("window_timestamp", desc=True)
        .limit(1)
        .execute()
    )

    if not result.data:
        return {
            "application_id": app_id,
            "anomaly_detected": False,
            "mode": "advisory",
            "severity": "LOW",
            "summary": "No anomaly detected",
            "window_timestamp": None,
            "score": 0,
            "root_cause": None,
            "evidence": {},
            "created_at": None,
        }

    row = result.data[0]

    severity = (row.get("severity") or "LOW").upper()
    anomaly_detected = severity not in ["LOW", "NORMAL", "NONE"]

    return {
        "id": row.get("id"),
        "application_id": str(row.get("application_id")),
        "anomaly_detected": anomaly_detected,
        "mode": "diagnostic" if anomaly_detected else "advisory",
        "severity": severity,
        "summary": f"Latest anomaly severity is {severity} with root cause {row.get('root_cause') or 'unknown'}.",
        "window_timestamp": row.get("window_timestamp"),
        "score": row.get("score"),
        "root_cause": row.get("root_cause"),
        "evidence": row.get("evidence", {}),
        "created_at": row.get("created_at"),
    }


def get_anomalies_by_time_window(app_id: str, question: str) -> list[dict]:
    supabase = get_supabase_client()
    start_time, end_time = parse_time_window_from_question(question)

    query = (
        supabase.table("anomalies")
        .select("*")
        .eq("application_id", app_id)
        .order("window_timestamp", desc=False)
    )

    if start_time and end_time:
        query = query.gte("window_timestamp", start_time).lte("window_timestamp", end_time)

    result = query.execute()
    rows = result.data or []

    formatted = []
    for row in rows:
        severity = (row.get("severity") or "LOW").upper()
        formatted.append(
            {
                "id": row.get("id"),
                "application_id": str(row.get("application_id")),
                "window_timestamp": row.get("window_timestamp"),
                "score": row.get("score"),
                "severity": severity,
                "root_cause": row.get("root_cause"),
                "evidence": row.get("evidence", {}),
                "created_at": row.get("created_at"),
            }
        )

    return formatted