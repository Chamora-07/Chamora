from app.core.supabase_client import get_supabase_client
from app.services.time_parser_service import parse_time_window


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


def format_anomaly_row(row: dict) -> dict:
    return {
        "id": row.get("id"),
        "application_id": str(row.get("application_id")),
        "window_timestamp": row.get("window_timestamp"),
        "score": row.get("score"),
        "severity": (row.get("severity") or "LOW").upper(),
        "root_cause": row.get("root_cause"),
        "evidence": row.get("evidence", {}),
        "created_at": row.get("created_at"),
    }


def get_anomalies_by_time_window(app_id: str, question: str) -> list[dict]:
    supabase = get_supabase_client()
    parsed_window = parse_time_window(question)

    query = (
        supabase.table("anomalies")
        .select("*")
        .eq("application_id", app_id)
        .order("window_timestamp", desc=False)
    )

    if parsed_window:
        query = (
            query
            .gte("window_timestamp", parsed_window["start_utc"])
            .lte("window_timestamp", parsed_window["end_utc"])
        )
    else:
        query = query.limit(5)

    result = query.execute()
    rows = result.data or []

    return [format_anomaly_row(row) for row in rows]