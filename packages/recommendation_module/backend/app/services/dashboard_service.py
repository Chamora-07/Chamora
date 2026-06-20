from .application_context_service import get_application_context
from .anomaly_query_service import get_latest_anomaly_for_app


def get_dashboard_data(app_id: str) -> dict:
    context = get_application_context(app_id)
    anomaly_state = get_latest_anomaly_for_app(app_id)

    return {
        "application": {
            "app_id": context["app_id"],
            "app_name": context["app_name"],
            "domain": context["domain"],
            "environment": context["environment"],
            "user_id": context["user_id"],
            "user_name": context["user_name"],
            "repo_url": context["repo_url"],
            "description": context.get("description", ""),
        },
        "metrics": context["metrics"],
        "containers": context["containers"],
        "tech_stack": context["tech_stack"],
        "anomaly": anomaly_state,
    }