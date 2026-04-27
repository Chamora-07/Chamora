import re
from app.core.supabase_client import get_supabase_client


def extract_cycle_numbers(question: str):
    """
    Extracts two test run IDs from a user question.

    Example:
    'Compare test run 1 and 2'
    -> returns (1, 2)
    """
    numbers = re.findall(r"\b\d+\b", question)

    if len(numbers) >= 2:
        return int(numbers[0]), int(numbers[1])

    return None, None


def extract_requested_metrics(question: str):
    """
    Minimal version.

    Current test_runs table does not store metrics yet, so we return
    a basic placeholder list if user mentions comparison-related words.
    """
    q = question.lower()

    supported = []

    if "response" in q or "latency" in q:
        supported.append("response_time")

    if "throughput" in q:
        supported.append("throughput")

    if "error" in q:
        supported.append("error_rate")

    if "cpu" in q:
        supported.append("cpu")

    if "memory" in q:
        supported.append("memory")

    if not supported:
        supported.append("basic_run_metadata")

    return supported


def get_test_run_by_id(run_id: int):
    supabase = get_supabase_client()

    result = (
        supabase.table("test_runs")
        .select("id,test_script_id,status,start_time,end_time,result_file_path")
        .eq("id", run_id)
        .limit(1)
        .execute()
    )

    if not result.data:
        return None

    return result.data[0]


def get_test_script_by_id(script_id):
    supabase = get_supabase_client()

    result = (
        supabase.table("test_scripts")
        .select("id,application_id,script_name,storage_path")
        .eq("id", script_id)
        .limit(1)
        .execute()
    )

    if not result.data:
        return None

    return result.data[0]


def get_test_cycle_comparison(app_id: str, run_a_id: int, run_b_id: int):
    """
    Minimal real integration using existing Supabase tables:

    test_runs:
    - id
    - test_script_id
    - status
    - start_time
    - end_time
    - result_file_path

    test_scripts:
    - id
    - application_id
    - script_name
    - storage_path

    Since metrics are not stored yet, this compares metadata only.
    """

    run_a = get_test_run_by_id(run_a_id)
    run_b = get_test_run_by_id(run_b_id)

    if not run_a or not run_b:
        return None

    script_a = get_test_script_by_id(run_a["test_script_id"])
    script_b = get_test_script_by_id(run_b["test_script_id"])

    if not script_a or not script_b:
        return None

    if str(script_a["application_id"]) != str(app_id) or str(script_b["application_id"]) != str(app_id):
        return None

    return {
        "application_id": app_id,
        "baseline_run_id": run_a_id,
        "target_run_id": run_b_id,
        "summary": (
            f"Basic comparison prepared for test run {run_a_id} and test run {run_b_id}. "
            "Only run metadata is available because detailed performance metrics are not stored yet."
        ),
        "regression_detected": False,
        "metrics": {
            "basic_run_metadata": {
                "baseline": {
                    "run_id": run_a["id"],
                    "script_name": script_a["script_name"],
                    "status": run_a["status"],
                    "start_time": run_a["start_time"],
                    "end_time": run_a["end_time"],
                    "result_file_path": run_a["result_file_path"],
                },
                "target": {
                    "run_id": run_b["id"],
                    "script_name": script_b["script_name"],
                    "status": run_b["status"],
                    "start_time": run_b["start_time"],
                    "end_time": run_b["end_time"],
                    "result_file_path": run_b["result_file_path"],
                },
                "difference": "Metric comparison unavailable",
                "difference_percent": "N/A",
            }
        },
    }