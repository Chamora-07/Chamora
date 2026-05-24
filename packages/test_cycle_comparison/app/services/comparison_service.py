"""
Comparison orchestrator: fetch N cycles in parallel, then run math.

Separates the I/O concerns (fetching from VM, loading catalog) from the
pure-function math in `comparison_math`, so the math is unit-testable
without any external dependencies.
"""

import asyncio
from typing import Dict, List, Optional

from app.services.comparison_math import compare
from app.services.cycle_metrics_fetcher import FetchError, fetch_cycle_metrics
from app.services.llm_summary import DEFAULT_TOP_N, generate_summary
from app.services.metric_catalog import SINGLE_CYCLE_DEFAULT_METRICS, catalog


async def run_comparison(
    cycle_ids: List[int],
    metric_keys: Optional[List[str]],
    endpoint_ids: List[int],
    baseline_cycle_id: Optional[int] = None,
    group_by_endpoint: bool = False,
    regression_threshold_pct: float = 10.0,
    aggregation_overrides: Optional[Dict[str, str]] = None,
    thresholds: Optional[Dict[str, dict]] = None,
    include_summary: bool = True,
    summary_top_n: int = DEFAULT_TOP_N,
) -> dict:
    """
    Fetch metrics for every cycle in parallel, then return the comparison.
    Raises FetchError (with status_code) on any unrecoverable problem.

    In single-cycle mode (`len(cycle_ids) == 1`), if `metric_keys` is omitted
    we fall back to SINGLE_CYCLE_DEFAULT_METRICS, and `thresholds` (if any)
    is applied per metric.
    """
    if baseline_cycle_id is not None and baseline_cycle_id not in cycle_ids:
        raise FetchError(
            f"baseline_cycle_id {baseline_cycle_id} must be in cycle_ids "
            f"{cycle_ids}",
            422,
        )

    # Single-cycle default metric list
    if not metric_keys:
        if len(cycle_ids) == 1:
            metric_keys = list(SINGLE_CYCLE_DEFAULT_METRICS)
        else:
            raise FetchError(
                "metric_keys is required when comparing more than one cycle.",
                422,
            )

    # Fetch all cycles in parallel. Any one failure aborts the request —
    # comparisons over partial cycle sets would mislead the LLM.
    fetch_tasks = [
        fetch_cycle_metrics(
            cycle_id=cid,
            metric_keys=metric_keys,
            endpoint_ids=endpoint_ids,
            aggregation_overrides=aggregation_overrides,
            group_by_endpoint=group_by_endpoint,
        )
        for cid in cycle_ids
    ]
    cycle_results = await asyncio.gather(*fetch_tasks)

    # Sanity: every cycle must belong to the same application
    app_ids = {c["application_id"] for c in cycle_results}
    if len(app_ids) > 1:
        raise FetchError(
            f"All cycles must belong to the same application; got app_ids={app_ids}",
            422,
        )

    application_id = next(iter(app_ids))

    full_catalog = await catalog.get_for_app(application_id)
    catalog_by_key = {m["key"]: m for m in full_catalog}

    try:
        report = compare(
            cycle_results=cycle_results,
            catalog_by_key=catalog_by_key,
            baseline_cycle_id=baseline_cycle_id,
            regression_threshold_pct=regression_threshold_pct,
            thresholds=thresholds,
        )
    except ValueError as e:
        raise FetchError(str(e), 422)

    response = {
        "application_id": application_id,
        "endpoint_ids": endpoint_ids,
        **report,
    }

    if include_summary:
        # generate_summary never raises — fallback covers Groq failures.
        response["summary"] = await generate_summary(response, top_n=summary_top_n)

    return response
