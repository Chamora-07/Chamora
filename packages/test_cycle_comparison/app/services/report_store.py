"""
Persistence for comparison reports.

Every successful /compare run is written to the `comparison_results` table
(DDL: sql/001_comparison_results.sql). A row carries three things:

  * denormalised columns  — cheap history queries without opening the jsonb
  * `report`              — the exact /compare response body
  * `display`             — everything ComparisonResultsPage.tsx renders that
                            is not in `report`: cycle labels/status badges,
                            metric metadata, and the metric-breakdown table
                            flattened into rows

The flattened rows matter for the recommendation module: it can read a past
comparison straight off the row instead of re-deriving the page's logic, or
re-querying VictoriaMetrics — which cannot answer for a cycle window that has
since rolled out of retention.

Saving is best-effort. A storage failure is logged and surfaced on the
response as `saved: false`; it never fails the comparison itself.
"""

import json
import logging
import math
from typing import Any, Dict, List, Optional

from app.core.supabase_client import get_supabase_client
from app.services.db_lookups import get_cycles_display_meta

logger = logging.getLogger(__name__)

TABLE = "comparison_results"

# Columns returned for history listings — everything except the two heavy
# jsonb payloads, so listing 50 comparisons stays small.
LIST_COLUMNS = (
    "id,application_id,user_id,mode,cycle_ids,baseline_cycle_id,endpoint_ids,"
    "metric_keys,group_by_endpoint,regression_threshold_pct,thresholds_applied,"
    "regression_count,improvement_count,unchanged_count,violation_count,"
    "ok_count,no_threshold_count,metric_count,missing_metric_keys,"
    "summary_text,summary_source,summary_model,top_metric_key,"
    "top_metric_significance,created_at"
)

# Worst-first ordering, mirroring the status column on the results page.
_CLASSIFICATION_ORDER = {"regressed": 0, "unchanged": 1, "improved": 2}


# --------------------------------------------------------------------------- #
# Sanitisation
# --------------------------------------------------------------------------- #

def _clean(value: Any) -> Any:
    """
    Recursively replace non-finite floats with None.

    Postgres `jsonb` rejects NaN and Infinity outright, and the math layer can
    produce either — e.g. `cv` when the cross-cycle mean is 0. Without this
    the whole insert fails.
    """
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, dict):
        return {k: _clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_clean(v) for v in value]
    return value


def _humanize(key: str) -> str:
    return " ".join(w.capitalize() for w in key.split("_"))


# --------------------------------------------------------------------------- #
# Display payload — what the page renders
# --------------------------------------------------------------------------- #

def _worst_classification(
    comparisons: Optional[List[dict]], baseline_cycle_id: int
) -> Optional[str]:
    """The status badge: worst classification among the non-baseline cycles."""
    candidates = [
        c.get("classification")
        for c in (comparisons or [])
        if c.get("cycle_id") != baseline_cycle_id and c.get("classification")
    ]
    if not candidates:
        return None
    return min(candidates, key=lambda c: _CLASSIFICATION_ORDER.get(c, 3))


def _axis_row(
    metric_key: str,
    meta: dict,
    axis: dict,
    cycles: List[dict],
    cycle_labels: Dict[int, str],
    baseline_cycle_id: int,
    mode: str,
    endpoint_id: Optional[str] = None,
) -> dict:
    """Flatten one axis (a metric, or a metric x endpoint pair) into a row."""
    value_by_cycle = {
        v.get("cycle_id"): v.get("value") for v in axis.get("values", [])
    }
    comparison_by_cycle = {
        c.get("cycle_id"): c for c in (axis.get("comparisons") or [])
    }

    values = []
    for cycle in cycles:
        cid = cycle.get("cycle_id")
        comparison = comparison_by_cycle.get(cid) or {}
        values.append({
            "cycle_id": cid,
            "cycle_label": cycle_labels.get(cid, f"Cycle #{cid}"),
            "value": value_by_cycle.get(cid),
            "is_baseline": cid == baseline_cycle_id,
            "pct_change": comparison.get("pct_change"),
            "diff": comparison.get("diff"),
            "classification": comparison.get("classification"),
        })

    threshold_check = axis.get("threshold_check")
    if mode == "threshold":
        status = (threshold_check or {}).get("classification")
    else:
        status = _worst_classification(axis.get("comparisons"), baseline_cycle_id)

    significance = axis.get("significance") or {}

    return {
        "metric_key": metric_key,
        "endpoint_id": endpoint_id,
        "label": meta.get("label") or _humanize(metric_key),
        "category": meta.get("category") or axis.get("category"),
        "aggregation": meta.get("aggregation") or axis.get("aggregation"),
        "unit": meta.get("unit") or axis.get("unit"),
        "higher_is_worse": meta.get("higher_is_worse"),
        "rank": significance.get("rank"),
        "significance": significance.get("score"),
        "comparable": axis.get("comparable"),
        "values": values,
        "status": status,
        "threshold_check": threshold_check,
        "cross_cycle_stats": axis.get("cross_cycle_stats"),
    }


def build_display(
    report: dict,
    catalog_by_key: Dict[str, dict],
    app_name: Optional[str],
) -> dict:
    """
    Assemble the render payload for one report: the cycle cards, the metric
    metadata the picker showed, and the metric-breakdown rows in the same
    order and with the same status the page displays.
    """
    cycles = report.get("cycles", [])
    baseline_cycle_id = report.get("baseline_cycle_id")
    mode = report.get("mode", "baseline")

    # Cycle cards — script_name is the column label, status is the badge.
    cycle_ids = [c.get("cycle_id") for c in cycles if c.get("cycle_id") is not None]
    try:
        cycle_meta = get_cycles_display_meta(cycle_ids)
    except Exception as e:  # never block a save on a label lookup
        logger.warning(f"Could not load cycle display metadata: {e}")
        cycle_meta = {}

    cycle_cards = []
    cycle_labels: Dict[int, str] = {}
    for cycle in cycles:
        cid = cycle.get("cycle_id")
        meta = cycle_meta.get(cid, {})
        label = meta.get("script_name") or f"Cycle #{cid}"
        cycle_labels[cid] = label
        cycle_cards.append({
            "cycle_id": cid,
            "label": label,
            "role": "baseline" if cid == baseline_cycle_id else "target",
            "test_script_id": meta.get("test_script_id"),
            "status": meta.get("status"),
            "start_time": cycle.get("start_time"),
            "end_time": cycle.get("end_time"),
            "duration_seconds": cycle.get("duration_seconds"),
        })

    # Metric-breakdown rows. Grouped metrics fan out to one row per endpoint.
    rows: List[dict] = []
    for metric_key, result in (report.get("metrics") or {}).items():
        meta = catalog_by_key.get(metric_key, {})
        by_endpoint = result.get("by_endpoint")
        if by_endpoint:
            for endpoint_id, axis in by_endpoint.items():
                rows.append(_axis_row(
                    metric_key, meta, axis, cycles, cycle_labels,
                    baseline_cycle_id, mode, endpoint_id=endpoint_id,
                ))
        else:
            rows.append(_axis_row(
                metric_key, meta, result, cycles, cycle_labels,
                baseline_cycle_id, mode,
            ))

    # Same ordering the page uses: significance rank ascending, unranked last.
    rows.sort(key=lambda r: r["rank"] if r.get("rank") is not None else 999)

    metric_keys = sorted({r["metric_key"] for r in rows})
    return {
        "app_name": app_name,
        "application_id": report.get("application_id"),
        "mode": mode,
        "cycles": cycle_cards,
        "metrics": [catalog_by_key[k] for k in metric_keys if k in catalog_by_key],
        "rows": rows,
    }


# --------------------------------------------------------------------------- #
# Row assembly
# --------------------------------------------------------------------------- #

def build_record(
    report: dict,
    display: dict,
    user_id: Optional[int] = None,
) -> dict:
    """Map a report + display payload onto the comparison_results columns."""
    summary = report.get("summary") or {}
    rows = display.get("rows", [])

    ranked = [r for r in rows if r.get("rank") is not None]
    top = min(ranked, key=lambda r: r["rank"]) if ranked else None

    record = {
        "application_id": report.get("application_id"),
        "user_id": user_id,
        "mode": report.get("mode", "baseline"),
        "cycle_ids": [c.get("cycle_id") for c in report.get("cycles", [])],
        "baseline_cycle_id": report.get("baseline_cycle_id"),
        "endpoint_ids": report.get("endpoint_ids", []),
        "metric_keys": sorted((report.get("metrics") or {}).keys()),
        "group_by_endpoint": report.get("group_by_endpoint", False),
        "regression_threshold_pct": report.get("regression_threshold_pct"),
        "thresholds_applied": report.get("thresholds_applied", False),
        "regression_count": report.get("regression_count", 0),
        "improvement_count": report.get("improvement_count", 0),
        "unchanged_count": report.get("unchanged_count", 0),
        "violation_count": report.get("violation_count", 0),
        "ok_count": report.get("ok_count", 0),
        "no_threshold_count": report.get("no_threshold_count", 0),
        "metric_count": len(report.get("metrics") or {}),
        "missing_metric_keys": report.get("missing_metric_keys", []),
        "summary_text": summary.get("summary"),
        "summary_source": summary.get("source"),
        "summary_model": summary.get("model"),
        "summary_error": summary.get("error"),
        "top_metric_key": top["metric_key"] if top else None,
        "top_metric_significance": top.get("significance") if top else None,
        "report": report,
        "display": display,
    }
    return _clean(record)


# --------------------------------------------------------------------------- #
# CRUD
# --------------------------------------------------------------------------- #

def save_comparison_result(record: dict) -> int:
    """Insert one comparison result and return the new id."""
    supabase = get_supabase_client()
    result = supabase.table(TABLE).insert(record).execute()
    if not result.data:
        raise RuntimeError("insert returned no rows")
    return result.data[0]["id"]


def list_comparison_results(
    application_id: Optional[int] = None,
    user_id: Optional[int] = None,
    cycle_id: Optional[int] = None,
    limit: int = 20,
    offset: int = 0,
) -> List[dict]:
    """
    History listing, newest first. Omits `report`/`display` — use
    `get_comparison_result` to load one in full.
    """
    supabase = get_supabase_client()
    query = supabase.table(TABLE).select(LIST_COLUMNS)

    if application_id is not None:
        query = query.eq("application_id", application_id)
    if user_id is not None:
        query = query.eq("user_id", user_id)
    if cycle_id is not None:
        # jsonb containment — matches rows whose cycle_ids array holds cycle_id.
        # The value must be a JSON *string*: postgrest-py renders a Python list
        # as PostgREST array syntax ({67}), which jsonb `@>` will not accept.
        query = query.contains("cycle_ids", json.dumps([cycle_id]))

    result = (
        query.order("created_at", desc=True)
        .range(offset, offset + limit - 1)
        .execute()
    )
    return result.data or []


def get_comparison_result(result_id: int) -> Optional[dict]:
    """Load one saved comparison in full, including `report` and `display`."""
    supabase = get_supabase_client()
    result = (
        supabase.table(TABLE)
        .select("*")
        .eq("id", result_id)
        .limit(1)
        .execute()
    )
    return result.data[0] if result.data else None


def delete_comparison_result(result_id: int) -> bool:
    """Delete one saved comparison. Returns True if a row was removed."""
    supabase = get_supabase_client()
    result = (
        supabase.table(TABLE)
        .delete()
        .eq("id", result_id)
        .execute()
    )
    return bool(result.data)
