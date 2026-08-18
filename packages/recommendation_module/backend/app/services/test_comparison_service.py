import json
import re
from datetime import datetime
from typing import Optional

from ..core.supabase_client import get_supabase_client
from ..core.config import settings


def extract_cycle_numbers(question: str):
    numbers = re.findall(r"\b\d+\b", question)
    if len(numbers) < 2:
        return None, None
    return int(numbers[0]), int(numbers[1])


METRIC_KEYWORDS = {
    "response time": "response_time",
    "throughput": "throughput",
    "error rate": "error_rate",
    "latency": "latency",
    "cpu": "cpu",
    "memory": "memory",
}


def extract_requested_metrics(question: str):
    q = question.lower()
    return [canonical for phrase, canonical in METRIC_KEYWORDS.items() if phrase in q]


def _fetch_test_run(run_id: int) -> Optional[dict]:
    """Fetch a single test_runs row by its primary key (id)."""
    supabase = get_supabase_client()
    result = (
        supabase.table("test_runs")
        .select("id,test_script_id,status,start_time,end_time,result_file_path")
        .eq("id", run_id)
        .limit(1)
        .execute()
    )
    return result.data[0] if result.data else None


def _fetch_result_file_bytes(result_file_path: str) -> Optional[bytes]:
    """Download the raw NDJSON result file from Supabase Storage."""
    supabase = get_supabase_client()
    bucket_name = getattr(settings, "SUPABASE_STORAGE_TEST_RESULTS_BUCKET", "k6_results")

    try:
        return supabase.storage.from_(bucket_name).download(result_file_path)
    except Exception:
        return None


def _parse_k6_ndjson(file_bytes: bytes) -> dict:
    """
    Parses k6's raw NDJSON (--out json) format and aggregates key metrics.
    Each line is either {"type": "Metric", ...} (a definition, skip) or
    {"type": "Point", "metric": name, "data": {"value": ..., "tags": {...}, "time": ...}}.

    Note: this file can be 15-20MB+ for large load tests. This does a single
    streaming pass over the decoded text rather than loading it as one JSON
    blob, keeping memory bounded to the running aggregates, not the raw file.
    """
    duration_sum = 0.0
    duration_count = 0
    durations_sample = []  # bounded sample for p95 approximation on huge files

    request_count = 0
    failed_count = 0
    first_timestamp = None
    last_timestamp = None

    MAX_SAMPLE = 50000  # cap p95 sample size to bound memory on very large files

    text = file_bytes.decode("utf-8")
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue

        if obj.get("type") != "Point":
            continue

        metric = obj.get("metric")
        data = obj.get("data", {})
        value = data.get("value")
        timestamp = data.get("time")

        if timestamp:
            if first_timestamp is None:
                first_timestamp = timestamp
            last_timestamp = timestamp

        if metric == "http_req_duration" and value is not None:
            duration_sum += value
            duration_count += 1
            if len(durations_sample) < MAX_SAMPLE:
                durations_sample.append(value)

        elif metric == "http_reqs":
            request_count += 1

        elif metric == "http_req_failed" and value is not None:
            # k6 reports this as a rate metric: 0 = passed, 1 = failed, per request.
            if value >= 1:
                failed_count += 1

    if duration_count == 0:
        return {}

    avg_response_time = duration_sum / duration_count

    sorted_sample = sorted(durations_sample)
    p95_index = int(len(sorted_sample) * 0.95)
    p95_response_time = sorted_sample[min(p95_index, len(sorted_sample) - 1)] if sorted_sample else None

    duration_seconds = None
    if first_timestamp and last_timestamp:
        t0 = datetime.fromisoformat(first_timestamp.replace("Z", "+00:00"))
        t1 = datetime.fromisoformat(last_timestamp.replace("Z", "+00:00"))
        duration_seconds = max((t1 - t0).total_seconds(), 1)

    throughput = (request_count / duration_seconds) if duration_seconds else None
    denom = request_count or duration_count
    error_rate = (failed_count / denom * 100) if denom else 0.0

    return {
        "response_time": round(avg_response_time, 2),
        "latency": round(p95_response_time, 2) if p95_response_time is not None else None,
        "throughput": round(throughput, 2) if throughput is not None else None,
        "error_rate": round(error_rate, 2),
        "total_requests": request_count,
    }


def get_test_cycle_comparison(app_id, cycle_a: int, cycle_b: int, metrics: list[str]) -> dict:
    """
    Real comparison between two test_runs rows.
    cycle_a / cycle_b are test_runs.id values. baseline = cycle_a, target = cycle_b.

    IMPORTANT: 'cpu' and 'memory' are NOT available from k6 result files —
    k6 only measures client-side HTTP metrics, not host resource usage.
    Those come from cAdvisor/Prometheus/VictoriaMetrics instead and are not
    wired up here yet.
    """
    run_a = _fetch_test_run(cycle_a)
    run_b = _fetch_test_run(cycle_b)

    if not run_a or not run_b:
        missing = []
        if not run_a:
            missing.append(str(cycle_a))
        if not run_b:
            missing.append(str(cycle_b))
        return {
            "summary": f"Could not find test run(s): {', '.join(missing)}.",
            "regression_detected": False,
            "metrics": {},
            "error": "run_not_found",
        }

    for run, label in ((run_a, cycle_a), (run_b, cycle_b)):
        if run["status"] != "completed" or not run.get("result_file_path"):
            return {
                "summary": (
                    f"Run {label} has status '{run['status']}' and no completed results "
                    f"are available for comparison."
                ),
                "regression_detected": False,
                "metrics": {},
                "error": "run_not_completed",
            }

    unsupported = [m for m in metrics if m in ("cpu", "memory")]
    supported_metrics = [m for m in metrics if m not in ("cpu", "memory")]

    file_a = _fetch_result_file_bytes(run_a["result_file_path"])
    file_b = _fetch_result_file_bytes(run_b["result_file_path"])

    if file_a is None or file_b is None:
        return {
            "summary": "Result files could not be downloaded for one or both runs.",
            "regression_detected": False,
            "metrics": {},
            "error": "result_download_failed",
        }

    parsed_a = _parse_k6_ndjson(file_a)
    parsed_b = _parse_k6_ndjson(file_b)

    if not parsed_a or not parsed_b:
        return {
            "summary": "Result files did not contain usable request data.",
            "regression_detected": False,
            "metrics": {},
            "error": "no_data_points",
        }

    comparison_metrics = {}
    regression_detected = False
    worse_if_higher = {"response_time", "error_rate", "latency"}

    for metric in supported_metrics:
        baseline = parsed_a.get(metric)
        target = parsed_b.get(metric)

        if baseline is None or target is None:
            continue

        difference = target - baseline
        difference_percent = round((difference / baseline) * 100, 2) if baseline else 0.0

        if metric in worse_if_higher and difference_percent > 10:
            regression_detected = True
        if metric == "throughput" and difference_percent < -10:
            regression_detected = True

        comparison_metrics[metric] = {
            "baseline": baseline,
            "target": target,
            "difference": round(difference, 2),
            "difference_percent": difference_percent,
        }

    summary_parts = []
    if comparison_metrics:
        summary_parts.append(
            f"Compared run {cycle_a} (baseline) against run {cycle_b} (target) "
            f"across {len(comparison_metrics)} metric(s)."
        )
    else:
        summary_parts.append(
            f"None of the requested metrics were found in the results for runs {cycle_a} and {cycle_b}."
        )
    if unsupported:
        summary_parts.append(
            f"Note: {', '.join(unsupported)} could not be compared — k6 result "
            f"files do not include host resource metrics."
        )

    return {
        "summary": " ".join(summary_parts),
        "regression_detected": regression_detected,
        "metrics": comparison_metrics,
    }