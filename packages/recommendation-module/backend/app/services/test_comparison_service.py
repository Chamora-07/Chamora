import re


def extract_cycle_numbers(question):
    matches = re.findall(r"\b\d+\b", question)
    numbers = [int(x) for x in matches]
    if len(numbers) >= 2:
        return numbers[0], numbers[1]
    return None, None


def extract_requested_metrics(question):
    q = question.lower()

    metric_keywords = {
        "response time": "response_time",
        "throughput": "throughput",
        "error rate": "error_rate",
        "cpu": "cpu",
        "memory": "memory",
        "latency": "latency",
    }

    found = [value for key, value in metric_keywords.items() if key in q]
    return found


def get_test_cycle_comparison(app_id, cycle_a, cycle_b, metrics):
    return {
        "application_id": app_id,
        "baseline_cycle": cycle_a,
        "target_cycle": cycle_b,
        "metrics": {
            "response_time": {
                "baseline": 320,
                "target": 470,
                "difference": 150,
                "difference_percent": 46.9
            },
            "throughput": {
                "baseline": 180,
                "target": 150,
                "difference": -30,
                "difference_percent": -16.7
            },
            "cpu": {
                "baseline": 68,
                "target": 79,
                "difference": 11,
                "difference_percent": 16.2
            },
            "memory": {
                "baseline": 63,
                "target": 71,
                "difference": 8,
                "difference_percent": 12.7
            }
        },
        "summary": f"Comparison prepared for cycle {cycle_a} and cycle {cycle_b}.",
        "regression_detected": True
    }