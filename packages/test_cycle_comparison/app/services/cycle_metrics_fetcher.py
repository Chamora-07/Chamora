"""
Cycle metrics fetcher.

For one test cycle, run PromQL queries (one per metric, or one per
metric × endpoint when grouping) against the application's VictoriaMetrics
instance and return per-metric scalars.

Concurrency capped via semaphore; per-query timeout + one retry on 5xx.
Failures yield `None` values in the response with an `error` string,
so a single bad metric never fails the whole request.
"""

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

import httpx

from app.core.config import settings
from app.services.db_lookups import get_cycle_context, get_endpoints
from app.services.metric_catalog import catalog
from app.services.promql_builder import SUPPORTED_AGGREGATIONS, build_cycle_query

logger = logging.getLogger(__name__)

MAX_CONCURRENT_QUERIES = 20
PER_QUERY_TIMEOUT = 5.0
RETRY_ATTEMPTS = 1
RETRY_BACKOFF_SECONDS = 0.2


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #

class FetchError(Exception):
    """Raised when the request cannot be processed (vs. partial data)."""

    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


async def fetch_cycle_metrics(
    cycle_id: int,
    metric_keys: List[str],
    endpoint_ids: List[int],
    aggregation_overrides: Optional[Dict[str, str]] = None,
    group_by_endpoint: bool = False,
) -> dict:
    """
    Fetch one scalar per (metric) — or per (metric, endpoint) when grouping —
    for the given cycle's time window.

    Always returns a dict; per-metric failures appear as `value: null` with an
    `error` string, and their keys are mirrored in the top-level `missing` list.
    """
    if not metric_keys:
        raise FetchError("metric_keys must contain at least one entry", 422)
    if not endpoint_ids:
        raise FetchError("endpoint_ids must contain at least one entry", 422)

    aggregation_overrides = aggregation_overrides or {}
    _validate_aggregation_overrides(aggregation_overrides)

    # --- 1. Cycle context -------------------------------------------------- #
    try:
        context = get_cycle_context(cycle_id)
    except ValueError as e:
        raise FetchError(str(e), 404)

    cycle = context["cycle"]
    application = context["application"]

    start_time = _parse_iso(cycle["start_time"])
    end_time = _parse_iso(cycle["end_time"]) if cycle.get("end_time") else None

    if end_time is None:
        raise FetchError(
            f"Cycle {cycle_id} is still running — metrics can only be fetched "
            f"after end_time is set.",
            409,
        )

    duration_seconds = (end_time - start_time).total_seconds()
    if duration_seconds <= 0:
        raise FetchError(
            f"Cycle {cycle_id} has non-positive duration "
            f"({duration_seconds}s) — check start_time/end_time.",
            422,
        )

    # --- 2. Endpoints ------------------------------------------------------ #
    endpoints = get_endpoints(endpoint_ids)
    if len(endpoints) != len(set(endpoint_ids)):
        found_ids = {e["id"] for e in endpoints}
        missing_ids = sorted(set(endpoint_ids) - found_ids)
        raise FetchError(f"Endpoints not found: {missing_ids}", 404)

    foreign = [
        e["id"] for e in endpoints
        if e["application_id"] != application["id"]
    ]
    if foreign:
        raise FetchError(
            f"Endpoints {foreign} do not belong to application "
            f"{application['id']} (cycle {cycle_id}'s application).",
            422,
        )

    # Order endpoints deterministically by the requested id order
    by_id = {e["id"]: e for e in endpoints}
    endpoints = [by_id[i] for i in endpoint_ids]

    # --- 3. Metric metadata ----------------------------------------------- #
    full_catalog = await catalog.get_for_app(application["id"])
    catalog_by_key = {m["key"]: m for m in full_catalog}

    unknown = [k for k in metric_keys if k not in catalog_by_key]
    if unknown:
        raise FetchError(
            f"Unknown metric keys for application {application['id']}: {unknown}",
            422,
        )

    # --- 4. Build queries -------------------------------------------------- #
    vm_base = _vm_base_from_url(application["victoria_metrics_url"])
    eval_time = end_time.timestamp()

    if group_by_endpoint:
        plan = _build_grouped_plan(
            metric_keys, catalog_by_key, endpoints,
            start_time, end_time, aggregation_overrides,
        )
    else:
        plan = _build_aggregated_plan(
            metric_keys, catalog_by_key, endpoints,
            start_time, end_time, aggregation_overrides,
        )

    # --- 5. Execute -------------------------------------------------------- #
    fetched = await _execute_plan(vm_base, plan, eval_time)

    # --- 6. Assemble ------------------------------------------------------- #
    return _assemble_response(
        cycle=cycle,
        application=application,
        endpoints=endpoints,
        start_time=start_time,
        end_time=end_time,
        duration_seconds=duration_seconds,
        plan=plan,
        fetched=fetched,
        group_by_endpoint=group_by_endpoint,
    )


# --------------------------------------------------------------------------- #
# Query planning
# --------------------------------------------------------------------------- #

@dataclass
class _PlanEntry:
    metric_key: str
    endpoint_id: Optional[int]      # None when aggregated
    query: str
    aggregated_across_endpoints: bool
    scoped_to_endpoints: bool       # whether endpoint selection mattered


def _build_aggregated_plan(
    metric_keys, catalog_by_key, endpoints,
    start_time, end_time, overrides,
) -> List[_PlanEntry]:
    entries = []
    for key in metric_keys:
        metric = catalog_by_key[key]
        scoped = metric.get("endpoint_scoped", False)
        scope_endpoints = endpoints if scoped else []
        query = build_cycle_query(
            metric, start_time, end_time, scope_endpoints,
            aggregation_override=overrides.get(key),
        )
        entries.append(_PlanEntry(
            metric_key=key,
            endpoint_id=None,
            query=query,
            aggregated_across_endpoints=(scoped and len(scope_endpoints) > 1),
            scoped_to_endpoints=scoped,
        ))
    return entries


def _build_grouped_plan(
    metric_keys, catalog_by_key, endpoints,
    start_time, end_time, overrides,
) -> List[_PlanEntry]:
    entries = []
    for key in metric_keys:
        metric = catalog_by_key[key]
        scoped = metric.get("endpoint_scoped", False)
        if not scoped:
            # No grouping possible — emit one entry without endpoint id
            query = build_cycle_query(
                metric, start_time, end_time, [],
                aggregation_override=overrides.get(key),
            )
            entries.append(_PlanEntry(
                metric_key=key,
                endpoint_id=None,
                query=query,
                aggregated_across_endpoints=False,
                scoped_to_endpoints=False,
            ))
            continue
        # One query per endpoint
        for ep in endpoints:
            query = build_cycle_query(
                metric, start_time, end_time, [ep],
                aggregation_override=overrides.get(key),
            )
            entries.append(_PlanEntry(
                metric_key=key,
                endpoint_id=ep["id"],
                query=query,
                aggregated_across_endpoints=False,
                scoped_to_endpoints=True,
            ))
    return entries


# --------------------------------------------------------------------------- #
# Execution
# --------------------------------------------------------------------------- #

async def _execute_plan(
    vm_base: str,
    plan: List[_PlanEntry],
    eval_time: float,
) -> Dict[int, Tuple[Optional[float], Optional[str]]]:
    """Returns {plan_index: (value, error)}."""
    sem = asyncio.Semaphore(MAX_CONCURRENT_QUERIES)
    results: Dict[int, Tuple[Optional[float], Optional[str]]] = {}

    async with httpx.AsyncClient(timeout=PER_QUERY_TIMEOUT) as client:
        async def run(idx: int, entry: _PlanEntry):
            async with sem:
                value, error = await _fetch_one_with_retry(
                    client, vm_base, entry.query, eval_time
                )
                results[idx] = (value, error)

        await asyncio.gather(*[run(i, e) for i, e in enumerate(plan)])

    return results


async def _fetch_one_with_retry(
    client: httpx.AsyncClient,
    vm_base: str,
    query: str,
    eval_time: float,
) -> Tuple[Optional[float], Optional[str]]:
    last_error: Optional[str] = None
    for attempt in range(RETRY_ATTEMPTS + 1):
        try:
            return await _fetch_one(client, vm_base, query, eval_time), None
        except httpx.HTTPStatusError as e:
            last_error = f"HTTP {e.response.status_code}"
            # Don't retry 4xx — the query is broken
            if e.response.status_code < 500 or attempt >= RETRY_ATTEMPTS:
                break
        except httpx.HTTPError as e:
            last_error = f"{type(e).__name__}: {e}"
            if attempt >= RETRY_ATTEMPTS:
                break
        except Exception as e:
            last_error = f"{type(e).__name__}: {e}"
            break
        await asyncio.sleep(RETRY_BACKOFF_SECONDS * (2 ** attempt))

    logger.debug(f"Query failed after retries: {query} -> {last_error}")
    return None, last_error


async def _fetch_one(
    client: httpx.AsyncClient,
    vm_base: str,
    query: str,
    eval_time: float,
) -> Optional[float]:
    url = f"{vm_base}/api/v1/query"
    response = await client.get(url, params={"query": query, "time": eval_time})
    response.raise_for_status()
    payload = response.json()

    result = payload.get("data", {}).get("result", [])
    if not result:
        return None

    value_pair = result[0].get("value")
    if not value_pair or len(value_pair) < 2:
        return None

    raw = value_pair[1]
    # VM returns numeric NaN as the string "NaN"
    if raw in ("NaN", "+Inf", "-Inf"):
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


# --------------------------------------------------------------------------- #
# Response assembly
# --------------------------------------------------------------------------- #

def _assemble_response(
    *, cycle, application, endpoints,
    start_time, end_time, duration_seconds,
    plan, fetched, group_by_endpoint,
) -> dict:
    metrics: Dict[str, dict] = {}
    missing: List[str] = []

    if group_by_endpoint:
        # Initialise nested structure
        for entry in plan:
            metrics.setdefault(entry.metric_key, {
                "scoped_to_endpoints": entry.scoped_to_endpoints,
                "by_endpoint": {},
                "value": None,
            })
        for idx, entry in enumerate(plan):
            value, error = fetched.get(idx, (None, "no result"))
            metric_block = metrics[entry.metric_key]
            if entry.endpoint_id is None:
                # Non-scoped metric — single value at top level
                metric_block["value"] = value
                metric_block["query"] = entry.query
                metric_block["error"] = error
            else:
                metric_block["by_endpoint"][str(entry.endpoint_id)] = {
                    "value": value,
                    "query": entry.query,
                    "error": error,
                }
            if value is None and entry.metric_key not in missing:
                missing.append(entry.metric_key)
    else:
        for idx, entry in enumerate(plan):
            value, error = fetched.get(idx, (None, "no result"))
            metrics[entry.metric_key] = {
                "value": value,
                "query": entry.query,
                "aggregated_across_endpoints": entry.aggregated_across_endpoints,
                "scoped_to_endpoints": entry.scoped_to_endpoints,
                "error": error,
            }
            if value is None:
                missing.append(entry.metric_key)

    return {
        "cycle_id": cycle["id"],
        "application_id": application["id"],
        "start_time": _to_iso(start_time),
        "end_time": _to_iso(end_time),
        "duration_seconds": duration_seconds,
        "endpoint_ids": [e["id"] for e in endpoints],
        "group_by_endpoint": group_by_endpoint,
        "metrics": metrics,
        "missing": missing,
        "fetched_at": _to_iso(datetime.now(timezone.utc)),
    }


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

def _validate_aggregation_overrides(overrides: Dict[str, str]) -> None:
    invalid = {
        key: agg for key, agg in overrides.items()
        if agg not in SUPPORTED_AGGREGATIONS
    }
    if invalid:
        raise FetchError(
            f"Unsupported aggregations in override: {invalid}. "
            f"Allowed: {SUPPORTED_AGGREGATIONS}",
            422,
        )


def _vm_base_from_url(vm_url: str) -> str:
    return vm_url.split("/api/")[0].rstrip("/")


def _parse_iso(value: str) -> datetime:
    """
    Parse an ISO 8601 timestamp from Supabase. Always returns a tz-aware
    datetime in UTC — Supabase emits naive strings for `timestamp` columns
    and tz-aware strings for `timestamptz`. We coerce both to UTC so
    arithmetic (end - start) never raises a "naive vs aware" TypeError.
    """
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _to_iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()
