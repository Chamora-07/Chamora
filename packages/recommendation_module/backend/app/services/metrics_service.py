import requests
from ..core.config import settings


def _query_victoria_metrics(query: str):
    url = f"{settings.VICTORIA_METRICS_URL}/api/v1/query"
    response = requests.get(url, params={"query": query}, timeout=5)
    response.raise_for_status()
    return response.json()


def get_application_metrics(app_id: str) -> dict:
    """
    For demo:
    - try live VictoriaMetrics first
    - if unavailable, return fallback data
    """

    # You can later map app_id -> container name properly
    container_name = "hms"

    cpu_query = f'rate(container_cpu_usage_seconds_total{{container="{container_name}"}}[5m]) * 100'
    memory_query = f'container_memory_usage_bytes{{container="{container_name}"}}'
    memory_limit_query = f'container_spec_memory_limit_bytes{{container="{container_name}"}}'

    try:
        cpu_response = _query_victoria_metrics(cpu_query)
        mem_response = _query_victoria_metrics(memory_query)
        mem_limit_response = _query_victoria_metrics(memory_limit_query)

        cpu_result = cpu_response.get("data", {}).get("result", [])
        mem_result = mem_response.get("data", {}).get("result", [])
        mem_limit_result = mem_limit_response.get("data", {}).get("result", [])

        cpu_percent = float(cpu_result[0]["value"][1]) if cpu_result else 34.0
        memory_used_bytes = float(mem_result[0]["value"][1]) if mem_result else 12.4 * 1024**3
        memory_total_bytes = float(mem_limit_result[0]["value"][1]) if mem_limit_result else 20 * 1024**3

        if memory_total_bytes <= 0:
            memory_total_bytes = 20 * 1024**3

        memory_percent = (memory_used_bytes / memory_total_bytes) * 100

        return {
            "cpu_percent": round(cpu_percent, 2),
            "memory_percent": round(memory_percent, 2),
            "memory_used": f"{round(memory_used_bytes / 1024**3, 1)} GB",
            "memory_total": f"{round(memory_total_bytes / 1024**3, 1)} GB",
            "source": "victoriametrics"
        }

    except Exception:
        return {
            "cpu_percent": 34.0,
            "memory_percent": 62.0,
            "memory_used": "12.4 GB",
            "memory_total": "20.0 GB",
            "source": "mock-fallback"
        }