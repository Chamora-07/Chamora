from ..core.supabase_client import get_supabase_client
from .metrics_service import get_application_metrics
from .docker_service import get_running_containers
from .github_service import extract_tech_stack
from .anomaly_query_service import get_latest_anomaly_for_app


def get_application_context(app_id: str) -> dict:
    supabase = get_supabase_client()

    app_result = (
        supabase.table("applications")
        .select("id,name,user_id,description,github_repo")
        .eq("id", app_id)
        .limit(1)
        .execute()
    )
    if not app_result.data:
        raise ValueError(f"Application '{app_id}' not found")
    app_row = app_result.data[0]

    user_result = (
        supabase.table("users")
        .select("id,username,email")
        .eq("id", app_row["user_id"])
        .limit(1)
        .execute()
    )
    user_row = user_result.data[0] if user_result.data else {
        "id": app_row["user_id"],
        "username": "Unknown User",
        "email": None,
    }

    repo_url = app_row.get("github_repo") or ""

    # NOTE: `domain` and `environment` do not exist as columns on `applications`
    # at all — they must either stay as sensible defaults here, or you need a
    # migration to add them if you want per-app values.
    domain = "unknown"
    environment = "unknown"

    metrics = get_application_metrics(app_id)
    containers = get_running_containers(app_id)

    tech_stack = extract_tech_stack(repo_url) if repo_url else {
        "frontend": "Unknown",
        "backend": "Unknown",
        "database": "Unknown",
        "apis": [],
        "evidence": ["github_repo not available in applications table"],
    }

    anomaly = get_latest_anomaly_for_app(app_id)

    return {
        "app_name": app_row["name"],
        "app_id": str(app_row["id"]),
        "domain": domain,
        "environment": environment,
        "description": app_row.get("description", ""),
        "user_id": str(user_row["id"]),
        "user_name": user_row.get("username", "Unknown User"),
        "user_email": user_row.get("email"),
        "repo_url": repo_url,
        "tech_stack": tech_stack,
        "metrics": metrics,
        "containers": containers,
        "anomaly": anomaly,
        "mode": anomaly.get("mode", "advisory"),
    }