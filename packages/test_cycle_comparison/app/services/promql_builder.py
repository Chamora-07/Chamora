"""
PromQL query builder for test-cycle comparisons.

Takes a metric metadata entry (from metric_catalog) plus a cycle time window
and a list of endpoints, and produces a single instant-eval PromQL query
that collapses the cycle to one scalar.

The builder honours:
  - metric.aggregation         (avg, p95, p99, max, min, sum, rate_avg, last, delta)
  - metric.endpoint_scoped     (whether to add a label filter at all)
  - metric.label_filter        (which Prometheus label takes endpoint values)
  - metric.multi_series_aggregator  (sum/avg/max when N endpoints selected)
  - per-request aggregation override
"""

import re
from datetime import datetime
from typing import List, Optional

SUPPORTED_AGGREGATIONS = (
    "avg", "p95", "p99", "max", "min", "sum", "rate_avg", "last", "delta",
)


def build_cycle_query(
    metric: dict,
    start_time: datetime,
    end_time: datetime,
    endpoints: List[dict],
    aggregation_override: Optional[str] = None,
) -> str:
    """
    Build a single PromQL expression for one (metric, cycle, endpoints) tuple.

    `endpoints` is a list of {"target_name": ..., "container_name": ...} dicts.
    For non-endpoint-scoped metrics, this list is ignored.
    """
    name = metric["key"]
    aggregation = aggregation_override or metric["aggregation"]
    label_filter = metric.get("label_filter")
    endpoint_scoped = metric.get("endpoint_scoped", False)
    msa = metric.get("multi_series_aggregator", "avg")

    window_seconds = max(1, int((end_time - start_time).total_seconds()))
    window = f"{window_seconds}s"

    selector = ""
    if endpoint_scoped and label_filter:
        selector = _build_selector(label_filter, endpoints)

    inner = _wrap_aggregation(name, selector, aggregation, window)

    # Roll up across series when multiple endpoints are selected for a scoped metric
    if endpoint_scoped and len(endpoints) > 1:
        inner = f"{msa}({inner})"

    return inner


def _wrap_aggregation(
    name: str, selector: str, aggregation: str, window: str
) -> str:
    if aggregation == "avg":
        return f"avg_over_time({name}{selector}[{window}])"
    if aggregation == "p95":
        return f"quantile_over_time(0.95, {name}{selector}[{window}])"
    if aggregation == "p99":
        return f"quantile_over_time(0.99, {name}{selector}[{window}])"
    if aggregation == "max":
        return f"max_over_time({name}{selector}[{window}])"
    if aggregation == "min":
        return f"min_over_time({name}{selector}[{window}])"
    if aggregation == "sum":
        return f"sum_over_time({name}{selector}[{window}])"
    if aggregation == "rate_avg":
        # Counters: short-window rate, then average across the cycle
        sec = int(window.rstrip("s")) if window.endswith("s") and window.rstrip("s").isdigit() else 60
        step = "1s" if sec < 60 else "1m"
        return f"avg_over_time(rate({name}{selector}[1m])[{window}:{step}])"
    if aggregation == "last":
        return f"{name}{selector}"
    if aggregation == "delta":
        return (
            f"max_over_time({name}{selector}[{window}]) "
            f"- min_over_time({name}{selector}[{window}])"
        )
    raise ValueError(f"Unsupported aggregation: {aggregation}")


def _build_selector(label_filter: str, endpoints: List[dict]) -> str:
    if not endpoints:
        return ""

    if label_filter == "job":
        values = [e["target_name"] for e in endpoints if e.get("target_name")]
    elif label_filter == "container_label_com_docker_compose_service":
        values = [e["container_name"] for e in endpoints if e.get("container_name")]
    else:
        values = []

    if not values:
        return ""

    if len(values) == 1:
        return f'{{{label_filter}="{_escape(values[0])}"}}'

    pattern = "|".join(re.escape(v) for v in values)
    return f'{{{label_filter}=~"{pattern}"}}'


def _escape(value: str) -> str:
    """Escape characters that would break a PromQL string literal."""
    return value.replace("\\", "\\\\").replace('"', '\\"')
