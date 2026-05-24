"""
Comparison math for test-cycle metrics.

Pure functions: given N (1–4) cycles' fetched metrics (Phase 3 shape) and
the metric catalog, produce per-metric comparisons against a baseline plus
cross-cycle stats and significance scores.

Behaviour by N:
  N=1    descriptive (values only, no comparisons)
  N=2    baseline vs target — diff, pct_change, classification
  N=3-4  baseline vs each + cross-cycle stats (mean, stddev, cv, trend slope)

Endpoint awareness:
  - If `group_by_endpoint=True` on the cycle results AND a metric is
    `endpoint_scoped`, the comparison is computed per endpoint and emitted
    under `by_endpoint[<id>]`.
  - Otherwise the comparison runs on the metric's aggregated scalar.

Significance:
  Each comparison gets a score = abs(pct_change) * weight, where weight
  depends on classification (regressed=1.0, improved=0.5, unchanged=0.1).
  Per-axis significance is the max across all comparisons for that axis.
  Ranks are assigned globally, smallest rank = most significant.
"""

import math
from typing import Dict, List, Optional, Tuple

# Weight applied to abs(pct_change) when computing significance.
# Regressions dominate so they float to the top of the LLM prompt.
_CLASSIFICATION_WEIGHT = {
    "regressed": 1.0,
    "improved": 0.5,
    "unchanged": 0.1,
}


# --------------------------------------------------------------------------- #
# Public entry point
# --------------------------------------------------------------------------- #

def compare(
    cycle_results: List[dict],
    catalog_by_key: Dict[str, dict],
    baseline_cycle_id: Optional[int] = None,
    regression_threshold_pct: float = 10.0,
    thresholds: Optional[Dict[str, dict]] = None,
) -> dict:
    if not cycle_results:
        raise ValueError("compare() needs at least one cycle result")

    grouped = cycle_results[0].get("group_by_endpoint", False)
    if not all(c.get("group_by_endpoint", False) == grouped for c in cycle_results):
        raise ValueError("All cycles must use the same group_by_endpoint setting")

    app_ids = {c.get("application_id") for c in cycle_results}
    if len(app_ids) > 1:
        raise ValueError(
            f"All cycles must belong to the same application; got {app_ids}"
        )

    cycle_ids = [c["cycle_id"] for c in cycle_results]
    if baseline_cycle_id is None:
        baseline_cycle_id = cycle_ids[0]
    if baseline_cycle_id not in cycle_ids:
        raise ValueError(
            f"baseline_cycle_id {baseline_cycle_id} not in cycle_ids {cycle_ids}"
        )

    # Mode selection. Thresholds only apply in single-cycle runs.
    single_cycle = len(cycle_results) == 1
    thresholds_applied = bool(single_cycle and thresholds)
    mode = "threshold" if thresholds_applied else "baseline"

    # Cycles ordered chronologically — used for trend slope only.
    cycles_chrono = sorted(cycle_results, key=lambda c: c.get("start_time", ""))

    # Union of metric keys across all cycles (handles fetcher partial results).
    all_keys = sorted({k for c in cycle_results for k in c.get("metrics", {}).keys()})

    metrics: Dict[str, dict] = {}
    for key in all_keys:
        meta = catalog_by_key.get(key, {})
        scoped = meta.get("endpoint_scoped", False)

        # In threshold mode, every metric gets a threshold_check block —
        # even if the user didn't set one for it (classified "no_threshold").
        if thresholds_applied:
            metric_threshold = (thresholds or {}).get(key, {})
        else:
            metric_threshold = None

        if grouped and scoped:
            metrics[key] = _compare_grouped_metric(
                key, meta, cycle_results, cycles_chrono,
                baseline_cycle_id, regression_threshold_pct,
                metric_threshold,
            )
        else:
            metrics[key] = _compare_aggregated_metric(
                key, meta, cycle_results, cycles_chrono,
                baseline_cycle_id, regression_threshold_pct,
                metric_threshold,
            )

    _assign_significance_ranks(metrics)
    counts = _count_outcomes(metrics)

    return {
        "cycles": [
            {
                "cycle_id": c["cycle_id"],
                "start_time": c.get("start_time"),
                "end_time": c.get("end_time"),
                "duration_seconds": c.get("duration_seconds"),
            }
            for c in cycle_results
        ],
        "baseline_cycle_id": baseline_cycle_id,
        "group_by_endpoint": grouped,
        "regression_threshold_pct": regression_threshold_pct,
        "mode": mode,
        "thresholds_applied": thresholds_applied,
        "metrics": metrics,
        **counts,
        "missing_metric_keys": sorted(
            {k for c in cycle_results for k in c.get("missing", [])}
        ),
    }


# --------------------------------------------------------------------------- #
# Aggregated single-axis comparison
# --------------------------------------------------------------------------- #

def _compare_aggregated_metric(
    key, meta, cycle_results, cycles_chrono, baseline_id, threshold,
    metric_threshold=None,
):
    values = [
        (c["cycle_id"], _safe_get(c, key, "value"))
        for c in cycle_results
    ]
    chrono = [
        _safe_get(c, key, "value") for c in cycles_chrono
    ]
    block = _build_axis_block(
        meta, values, chrono, baseline_id, threshold, metric_threshold,
    )
    block.update({
        "unit": meta.get("unit"),
        "category": meta.get("category"),
        "higher_is_worse": meta.get("higher_is_worse"),
        "aggregation": meta.get("aggregation"),
        "scoped_to_endpoints": meta.get("endpoint_scoped", False),
    })
    return block


def _safe_get(cycle: dict, metric_key: str, field: str):
    return (
        cycle.get("metrics", {})
        .get(metric_key, {})
        .get(field)
    )


# --------------------------------------------------------------------------- #
# Grouped (per-endpoint) comparison
# --------------------------------------------------------------------------- #

def _compare_grouped_metric(
    key, meta, cycle_results, cycles_chrono, baseline_id, threshold,
    metric_threshold=None,
):
    # Collect every endpoint id any cycle reported for this metric.
    endpoint_ids = sorted({
        eid
        for c in cycle_results
        for eid in (
            c.get("metrics", {}).get(key, {}).get("by_endpoint", {}).keys()
        )
    })

    by_endpoint: Dict[str, dict] = {}
    for eid in endpoint_ids:
        values = [
            (c["cycle_id"], _grouped_value(c, key, eid))
            for c in cycle_results
        ]
        chrono = [_grouped_value(c, key, eid) for c in cycles_chrono]
        by_endpoint[eid] = _build_axis_block(
            meta, values, chrono, baseline_id, threshold, metric_threshold,
        )

    return {
        "unit": meta.get("unit"),
        "category": meta.get("category"),
        "higher_is_worse": meta.get("higher_is_worse"),
        "aggregation": meta.get("aggregation"),
        "scoped_to_endpoints": True,
        "by_endpoint": by_endpoint,
    }


def _grouped_value(cycle: dict, metric_key: str, endpoint_id: str):
    return (
        cycle.get("metrics", {})
        .get(metric_key, {})
        .get("by_endpoint", {})
        .get(endpoint_id, {})
        .get("value")
    )


# --------------------------------------------------------------------------- #
# Single-axis math (shared between aggregated and grouped modes)
# --------------------------------------------------------------------------- #

def _build_axis_block(
    meta, values_per_cycle, chrono_values, baseline_id, threshold,
    metric_threshold=None,
) -> dict:
    baseline_value = next(
        (v for cid, v in values_per_cycle if cid == baseline_id), None
    )
    higher_is_worse = meta.get("higher_is_worse", True)

    values_out = [
        {"cycle_id": cid, "value": v} for cid, v in values_per_cycle
    ]

    comparisons = []
    for cid, v in values_per_cycle:
        if cid == baseline_id:
            continue
        comparisons.append(
            _build_comparison(baseline_value, v, cid, higher_is_worse, threshold)
        )

    valid_chrono = [v for v in chrono_values if isinstance(v, (int, float))]
    cross_cycle_stats = (
        _cross_cycle_stats(valid_chrono) if len(valid_chrono) >= 3 else None
    )

    # Threshold check (only ever populated when caller passes one — currently
    # only happens in single-cycle mode).
    threshold_check = None
    if metric_threshold is not None:
        threshold_check = _build_threshold_check(baseline_value, metric_threshold)

    sig_score = _significance_score_for_axis(comparisons, threshold_check)

    return {
        "values": values_out,
        "comparisons": comparisons,
        "cross_cycle_stats": cross_cycle_stats,
        "threshold_check": threshold_check,
        "significance": {"score": sig_score, "rank": None},
        "comparable": baseline_value is not None,
    }


# --------------------------------------------------------------------------- #
# Threshold check (single-cycle mode)
# --------------------------------------------------------------------------- #

def _build_threshold_check(value, threshold_spec: dict) -> dict:
    """
    Compare a single value against {min, max, target} bounds.

    Returns:
      {
        "threshold": {min, max, target},
        "value": <value>,
        "classification": "violated" | "ok" | "no_threshold" | "no_data",
        "violation": null OR {
            "kind": "above_max" | "below_min",
            "limit": <number>,
            "exceeded_by": <number>,
            "exceeded_by_pct": <number or null>,
        },
      }
    """
    min_v = threshold_spec.get("min")
    max_v = threshold_spec.get("max")
    target_v = threshold_spec.get("target")
    spec_out = {"min": min_v, "max": max_v, "target": target_v}

    if value is None:
        return {
            "threshold": spec_out,
            "value": None,
            "classification": "no_data",
            "violation": None,
        }

    if min_v is None and max_v is None:
        return {
            "threshold": spec_out,
            "value": value,
            "classification": "no_threshold",
            "violation": None,
        }

    if max_v is not None and value > max_v:
        excess = value - max_v
        pct = (excess / abs(max_v) * 100.0) if max_v != 0 else None
        return {
            "threshold": spec_out,
            "value": value,
            "classification": "violated",
            "violation": {
                "kind": "above_max",
                "limit": max_v,
                "exceeded_by": excess,
                "exceeded_by_pct": pct,
            },
        }

    if min_v is not None and value < min_v:
        shortfall = min_v - value
        pct = (shortfall / abs(min_v) * 100.0) if min_v != 0 else None
        return {
            "threshold": spec_out,
            "value": value,
            "classification": "violated",
            "violation": {
                "kind": "below_min",
                "limit": min_v,
                "exceeded_by": shortfall,
                "exceeded_by_pct": pct,
            },
        }

    return {
        "threshold": spec_out,
        "value": value,
        "classification": "ok",
        "violation": None,
    }


def _significance_score_for_axis(comparisons, threshold_check) -> float:
    """
    In threshold mode the score is the % overshoot of a violation.
    In baseline mode it stays the max-weighted pct_change (existing behaviour).
    """
    if threshold_check is not None:
        cls = threshold_check.get("classification")
        if cls != "violated":
            return 0.0
        pct = (threshold_check.get("violation") or {}).get("exceeded_by_pct")
        if pct is None:
            # Threshold was zero — flag it as significant but with finite score
            return 100.0
        return abs(pct)
    return _significance_score(comparisons)


def _build_comparison(
    baseline_value, target_value, target_cycle_id, higher_is_worse, threshold
) -> dict:
    if baseline_value is None or target_value is None:
        return {
            "cycle_id": target_cycle_id,
            "diff": None,
            "pct_change": None,
            "classification": None,
            "baseline_was_zero": baseline_value == 0,
        }

    diff = target_value - baseline_value
    if baseline_value == 0:
        return {
            "cycle_id": target_cycle_id,
            "diff": diff,
            "pct_change": None,
            "classification": None,
            "baseline_was_zero": True,
        }

    pct = (diff / abs(baseline_value)) * 100.0
    classification = _classify(pct, higher_is_worse, threshold)
    return {
        "cycle_id": target_cycle_id,
        "diff": diff,
        "pct_change": pct,
        "classification": classification,
        "baseline_was_zero": False,
    }


def _classify(pct: float, higher_is_worse: bool, threshold: float) -> str:
    if abs(pct) <= threshold:
        return "unchanged"
    moved_up = pct > 0
    if higher_is_worse:
        return "regressed" if moved_up else "improved"
    return "improved" if moved_up else "regressed"


def _cross_cycle_stats(values: List[float]) -> dict:
    n = len(values)
    mean = sum(values) / n
    variance = sum((x - mean) ** 2 for x in values) / n
    stddev = math.sqrt(variance)
    cv = (stddev / abs(mean)) if mean != 0 else None
    return {
        "mean": mean,
        "stddev": stddev,
        "cv": cv,
        "trend_slope_per_cycle": _linear_slope(values),
    }


def _linear_slope(values: List[float]) -> float:
    """OLS slope through (i, value_i). Units: value per cycle index."""
    n = len(values)
    if n < 2:
        return 0.0
    x_mean = (n - 1) / 2.0
    y_mean = sum(values) / n
    num = sum((i - x_mean) * (y - y_mean) for i, y in enumerate(values))
    den = sum((i - x_mean) ** 2 for i in range(n))
    return num / den if den != 0 else 0.0


def _significance_score(comparisons: List[dict]) -> float:
    score = 0.0
    for comp in comparisons:
        pct = comp.get("pct_change")
        if pct is None:
            continue
        weight = _CLASSIFICATION_WEIGHT.get(comp.get("classification"), 0.0)
        score = max(score, abs(pct) * weight)
    return score


# --------------------------------------------------------------------------- #
# Ranking + outcome counts
# --------------------------------------------------------------------------- #

def _iter_axis_blocks(metrics: Dict[str, dict]):
    """Yield every comparison axis (handles both aggregated + grouped shapes)."""
    for key, block in metrics.items():
        if "by_endpoint" in block and block["by_endpoint"]:
            for eid, sub in block["by_endpoint"].items():
                yield (key, eid, sub)
        else:
            yield (key, None, block)


def _assign_significance_ranks(metrics: Dict[str, dict]) -> None:
    axes = list(_iter_axis_blocks(metrics))
    axes.sort(key=lambda t: t[2]["significance"]["score"], reverse=True)
    for rank, (_, _, block) in enumerate(axes, start=1):
        block["significance"]["rank"] = rank


def _count_outcomes(metrics: Dict[str, dict]) -> dict:
    counts = {
        "regression_count": 0, "improvement_count": 0, "unchanged_count": 0,
        "violation_count": 0, "ok_count": 0, "no_threshold_count": 0,
    }
    for _, _, block in _iter_axis_blocks(metrics):
        for comp in block.get("comparisons", []):
            cls = comp.get("classification")
            if cls == "regressed":
                counts["regression_count"] += 1
            elif cls == "improved":
                counts["improvement_count"] += 1
            elif cls == "unchanged":
                counts["unchanged_count"] += 1
        tc = block.get("threshold_check")
        if tc is not None:
            tcls = tc.get("classification")
            if tcls == "violated":
                counts["violation_count"] += 1
            elif tcls == "ok":
                counts["ok_count"] += 1
            elif tcls == "no_threshold":
                counts["no_threshold_count"] += 1
    return counts
