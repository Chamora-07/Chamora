"""
Per-application metric catalog.

Discovery: pulls live metric names from the application's VictoriaMetrics
instance (`/api/v1/label/__name__/values`) and decorates each name with
metadata (unit, aggregation, regression direction, label scoping).

Metadata sources, in priority order:
  1. CURATED_METRICS — explicit overrides for high-signal metrics.
  2. infer_metric_metadata() — heuristic inference for everything else,
     based on Prometheus naming conventions.

Per-app result is cached in-process for CATALOG_CACHE_TTL seconds.
"""

import logging
import time
from typing import Dict, List, Optional, Tuple

import httpx

from app.core.config import settings
from app.core.supabase_client import get_supabase_client

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------- #
# Curated metric definitions
# --------------------------------------------------------------------------- #
# Each entry: { label, category, unit, aggregation, higher_is_worse,
#               endpoint_scoped, label_filter, multi_series_aggregator }
#
# aggregation values:
#   "avg"      -> avg_over_time(metric[window])
#   "p95"      -> quantile_over_time(0.95, metric[window])
#   "p99"      -> quantile_over_time(0.99, metric[window])
#   "max"      -> max_over_time(metric[window])
#   "min"      -> min_over_time(metric[window])
#   "sum"      -> sum_over_time(metric[window])
#   "rate_avg" -> avg_over_time(rate(metric[1m])[window:1m])
#   "last"     -> metric (instant)
#   "delta"    -> max_over_time - min_over_time over window
#
# label_filter values:
#   "job"                                            -> probe scoping
#   "container_label_com_docker_compose_service"     -> container scoping
#   None                                             -> not endpoint-scoped

CURATED_METRICS: Dict[str, dict] = {
    # ------------------------------ Probing ------------------------------ #
    "probe_duration_seconds": {
        "label": "Probe duration (p95)",
        "category": "Probing",
        "unit": "seconds",
        "aggregation": "p95",
        "higher_is_worse": True,
        "endpoint_scoped": True,
        "label_filter": "job",
        "multi_series_aggregator": "max",
    },
    "probe_http_duration_seconds": {
        "label": "HTTP phase duration",
        "category": "Probing",
        "unit": "seconds",
        "aggregation": "avg",
        "higher_is_worse": True,
        "endpoint_scoped": True,
        "label_filter": "job",
        "multi_series_aggregator": "max",
    },
    "probe_success": {
        "label": "Probe success ratio",
        "category": "Probing",
        "unit": "ratio",
        "aggregation": "avg",
        "higher_is_worse": False,
        "endpoint_scoped": True,
        "label_filter": "job",
        "multi_series_aggregator": "avg",
    },
    "probe_http_status_code": {
        "label": "HTTP status code (last)",
        "category": "Probing",
        "unit": "count",
        "aggregation": "last",
        "higher_is_worse": False,
        "endpoint_scoped": True,
        "label_filter": "job",
        "multi_series_aggregator": "max",
    },
    "probe_dns_lookup_time_seconds": {
        "label": "DNS lookup time",
        "category": "Probing",
        "unit": "seconds",
        "aggregation": "avg",
        "higher_is_worse": True,
        "endpoint_scoped": True,
        "label_filter": "job",
        "multi_series_aggregator": "max",
    },
    # ------------------------------ Container ---------------------------- #
    "container_cpu_usage_seconds_total": {
        "label": "Container CPU usage",
        "category": "Container",
        "unit": "cores",
        "aggregation": "rate_avg",
        "higher_is_worse": True,
        "endpoint_scoped": True,
        "label_filter": "container_label_com_docker_compose_service",
        "multi_series_aggregator": "sum",
    },
    "container_memory_usage_bytes": {
        "label": "Container memory usage",
        "category": "Container",
        "unit": "bytes",
        "aggregation": "avg",
        "higher_is_worse": True,
        "endpoint_scoped": True,
        "label_filter": "container_label_com_docker_compose_service",
        "multi_series_aggregator": "sum",
    },
    "container_memory_working_set_bytes": {
        "label": "Container memory working set",
        "category": "Container",
        "unit": "bytes",
        "aggregation": "avg",
        "higher_is_worse": True,
        "endpoint_scoped": True,
        "label_filter": "container_label_com_docker_compose_service",
        "multi_series_aggregator": "sum",
    },
    "container_network_receive_bytes_total": {
        "label": "Container network in",
        "category": "Container",
        "unit": "bytes/s",
        "aggregation": "rate_avg",
        "higher_is_worse": False,
        "endpoint_scoped": True,
        "label_filter": "container_label_com_docker_compose_service",
        "multi_series_aggregator": "sum",
    },
    "container_network_transmit_bytes_total": {
        "label": "Container network out",
        "category": "Container",
        "unit": "bytes/s",
        "aggregation": "rate_avg",
        "higher_is_worse": False,
        "endpoint_scoped": True,
        "label_filter": "container_label_com_docker_compose_service",
        "multi_series_aggregator": "sum",
    },
    "container_fs_reads_bytes_total": {
        "label": "Container disk reads",
        "category": "Container",
        "unit": "bytes/s",
        "aggregation": "rate_avg",
        "higher_is_worse": False,
        "endpoint_scoped": True,
        "label_filter": "container_label_com_docker_compose_service",
        "multi_series_aggregator": "sum",
    },
    "container_fs_writes_bytes_total": {
        "label": "Container disk writes",
        "category": "Container",
        "unit": "bytes/s",
        "aggregation": "rate_avg",
        "higher_is_worse": False,
        "endpoint_scoped": True,
        "label_filter": "container_label_com_docker_compose_service",
        "multi_series_aggregator": "sum",
    },
    "container_start_time_seconds": {
        "label": "Container start time",
        "category": "Container",
        "unit": "seconds",
        "aggregation": "delta",
        "higher_is_worse": True,
        "endpoint_scoped": True,
        "label_filter": "container_label_com_docker_compose_service",
        "multi_series_aggregator": "max",
    },
    "container_oom_events_total": {
        "label": "Container OOM events",
        "category": "Container",
        "unit": "count/s",
        "aggregation": "rate_avg",
        "higher_is_worse": True,
        "endpoint_scoped": True,
        "label_filter": "container_label_com_docker_compose_service",
        "multi_series_aggregator": "sum",
    },
    "container_processes": {
        "label": "Container processes",
        "category": "Container",
        "unit": "count",
        "aggregation": "avg",
        "higher_is_worse": False,
        "endpoint_scoped": True,
        "label_filter": "container_label_com_docker_compose_service",
        "multi_series_aggregator": "sum",
    },
    "container_threads": {
        "label": "Container threads",
        "category": "Container",
        "unit": "count",
        "aggregation": "avg",
        "higher_is_worse": False,
        "endpoint_scoped": True,
        "label_filter": "container_label_com_docker_compose_service",
        "multi_series_aggregator": "sum",
    },
    # ------------------------------ Host --------------------------------- #
    "node_cpu_seconds_total": {
        "label": "Host CPU usage",
        "category": "Host",
        "unit": "cores",
        "aggregation": "rate_avg",
        "higher_is_worse": True,
        "endpoint_scoped": False,
        "label_filter": None,
        "multi_series_aggregator": "sum",
    },
    "node_memory_MemAvailable_bytes": {
        "label": "Host memory available",
        "category": "Host",
        "unit": "bytes",
        "aggregation": "avg",
        "higher_is_worse": False,
        "endpoint_scoped": False,
        "label_filter": None,
        "multi_series_aggregator": "avg",
    },
    "node_memory_MemTotal_bytes": {
        "label": "Host memory total",
        "category": "Host",
        "unit": "bytes",
        "aggregation": "last",
        "higher_is_worse": False,
        "endpoint_scoped": False,
        "label_filter": None,
        "multi_series_aggregator": "avg",
    },
    "node_load1": {
        "label": "Host load (1m)",
        "category": "Host",
        "unit": "count",
        "aggregation": "avg",
        "higher_is_worse": True,
        "endpoint_scoped": False,
        "label_filter": None,
        "multi_series_aggregator": "avg",
    },
    "node_load5": {
        "label": "Host load (5m)",
        "category": "Host",
        "unit": "count",
        "aggregation": "avg",
        "higher_is_worse": True,
        "endpoint_scoped": False,
        "label_filter": None,
        "multi_series_aggregator": "avg",
    },
    "node_load15": {
        "label": "Host load (15m)",
        "category": "Host",
        "unit": "count",
        "aggregation": "avg",
        "higher_is_worse": True,
        "endpoint_scoped": False,
        "label_filter": None,
        "multi_series_aggregator": "avg",
    },
    "node_filesystem_avail_bytes": {
        "label": "Host disk available",
        "category": "Host",
        "unit": "bytes",
        "aggregation": "avg",
        "higher_is_worse": False,
        "endpoint_scoped": False,
        "label_filter": None,
        "multi_series_aggregator": "sum",
    },
    "node_disk_io_time_seconds_total": {
        "label": "Host disk IO time",
        "category": "Host",
        "unit": "seconds/s",
        "aggregation": "rate_avg",
        "higher_is_worse": True,
        "endpoint_scoped": False,
        "label_filter": None,
        "multi_series_aggregator": "sum",
    },
    "node_disk_read_bytes_total": {
        "label": "Host disk reads",
        "category": "Host",
        "unit": "bytes/s",
        "aggregation": "rate_avg",
        "higher_is_worse": False,
        "endpoint_scoped": False,
        "label_filter": None,
        "multi_series_aggregator": "sum",
    },
    "node_disk_written_bytes_total": {
        "label": "Host disk writes",
        "category": "Host",
        "unit": "bytes/s",
        "aggregation": "rate_avg",
        "higher_is_worse": False,
        "endpoint_scoped": False,
        "label_filter": None,
        "multi_series_aggregator": "sum",
    },
    "node_network_receive_bytes_total": {
        "label": "Host network in",
        "category": "Host",
        "unit": "bytes/s",
        "aggregation": "rate_avg",
        "higher_is_worse": False,
        "endpoint_scoped": False,
        "label_filter": None,
        "multi_series_aggregator": "sum",
    },
    "node_network_transmit_bytes_total": {
        "label": "Host network out",
        "category": "Host",
        "unit": "bytes/s",
        "aggregation": "rate_avg",
        "higher_is_worse": False,
        "endpoint_scoped": False,
        "label_filter": None,
        "multi_series_aggregator": "sum",
    },
    "node_filesystem_files_free": {
        "label": "Host inodes free",
        "category": "Host",
        "unit": "count",
        "aggregation": "avg",
        "higher_is_worse": False,
        "endpoint_scoped": False,
        "label_filter": None,
        "multi_series_aggregator": "sum",
    },
    # ----------- Application (Prometheus client / Go runtime / net_conntrack) -- #
    # These all use the `job` label (Prometheus' default scrape-target label),
    # so endpoint.target_name maps to the job value the app exposes.
    "process_cpu_seconds_total": {
        "label": "Process CPU time",
        "category": "Application",
        "unit": "cores",
        "aggregation": "rate_avg",
        "higher_is_worse": True,
        "endpoint_scoped": True,
        "label_filter": "job",
        "multi_series_aggregator": "sum",
    },
    "process_resident_memory_bytes": {
        "label": "Process resident memory",
        "category": "Application",
        "unit": "bytes",
        "aggregation": "avg",
        "higher_is_worse": True,
        "endpoint_scoped": True,
        "label_filter": "job",
        "multi_series_aggregator": "sum",
    },
    "process_open_fds": {
        "label": "Process open file descriptors",
        "category": "Application",
        "unit": "count",
        "aggregation": "avg",
        "higher_is_worse": True,
        "endpoint_scoped": True,
        "label_filter": "job",
        "multi_series_aggregator": "sum",
    },
    "process_network_receive_bytes_total": {
        "label": "Process network in",
        "category": "Application",
        "unit": "bytes/s",
        "aggregation": "rate_avg",
        "higher_is_worse": False,
        "endpoint_scoped": True,
        "label_filter": "job",
        "multi_series_aggregator": "sum",
    },
    "process_network_transmit_bytes_total": {
        "label": "Process network out",
        "category": "Application",
        "unit": "bytes/s",
        "aggregation": "rate_avg",
        "higher_is_worse": False,
        "endpoint_scoped": True,
        "label_filter": "job",
        "multi_series_aggregator": "sum",
    },
    "process_start_time_seconds": {
        "label": "Process restart detection",
        "category": "Application",
        "unit": "seconds",
        "aggregation": "delta",
        "higher_is_worse": True,
        "endpoint_scoped": True,
        "label_filter": "job",
        "multi_series_aggregator": "max",
    },
    "go_gc_duration_seconds": {
        "label": "Go GC pause duration",
        "category": "Application",
        "unit": "seconds",
        "aggregation": "p95",
        "higher_is_worse": True,
        "endpoint_scoped": True,
        "label_filter": "job",
        "multi_series_aggregator": "max",
    },
    "go_gc_pauses_seconds_count": {
        "label": "Go GC pause rate",
        "category": "Application",
        "unit": "count/s",
        "aggregation": "rate_avg",
        "higher_is_worse": True,
        "endpoint_scoped": True,
        "label_filter": "job",
        "multi_series_aggregator": "sum",
    },
    "go_gc_heap_allocs_bytes_total": {
        "label": "Go heap allocation rate",
        "category": "Application",
        "unit": "bytes/s",
        "aggregation": "rate_avg",
        "higher_is_worse": True,
        "endpoint_scoped": True,
        "label_filter": "job",
        "multi_series_aggregator": "sum",
    },
    "go_gc_heap_allocs_objects_total": {
        "label": "Go heap object alloc rate",
        "category": "Application",
        "unit": "count/s",
        "aggregation": "rate_avg",
        "higher_is_worse": True,
        "endpoint_scoped": True,
        "label_filter": "job",
        "multi_series_aggregator": "sum",
    },
    "go_gc_heap_live_bytes": {
        "label": "Go live heap bytes",
        "category": "Application",
        "unit": "bytes",
        "aggregation": "avg",
        "higher_is_worse": True,
        "endpoint_scoped": True,
        "label_filter": "job",
        "multi_series_aggregator": "sum",
    },
    "go_gc_cycles_total_gc_cycles_total": {
        "label": "Go GC cycle rate",
        "category": "Application",
        "unit": "count/s",
        "aggregation": "rate_avg",
        "higher_is_worse": True,
        "endpoint_scoped": True,
        "label_filter": "job",
        "multi_series_aggregator": "sum",
    },
    "go_memstats_heap_inuse_bytes": {
        "label": "Go heap in-use",
        "category": "Application",
        "unit": "bytes",
        "aggregation": "avg",
        "higher_is_worse": True,
        "endpoint_scoped": True,
        "label_filter": "job",
        "multi_series_aggregator": "sum",
    },
    "go_memstats_heap_alloc_bytes": {
        "label": "Go heap allocated",
        "category": "Application",
        "unit": "bytes",
        "aggregation": "avg",
        "higher_is_worse": True,
        "endpoint_scoped": True,
        "label_filter": "job",
        "multi_series_aggregator": "sum",
    },
    "go_memstats_alloc_bytes_total": {
        "label": "Go allocation rate",
        "category": "Application",
        "unit": "bytes/s",
        "aggregation": "rate_avg",
        "higher_is_worse": True,
        "endpoint_scoped": True,
        "label_filter": "job",
        "multi_series_aggregator": "sum",
    },
    "go_memstats_stack_inuse_bytes": {
        "label": "Go stack in-use",
        "category": "Application",
        "unit": "bytes",
        "aggregation": "avg",
        "higher_is_worse": True,
        "endpoint_scoped": True,
        "label_filter": "job",
        "multi_series_aggregator": "sum",
    },
    "go_memstats_next_gc_bytes": {
        "label": "Go next GC threshold",
        "category": "Application",
        "unit": "bytes",
        "aggregation": "avg",
        "higher_is_worse": False,
        "endpoint_scoped": True,
        "label_filter": "job",
        "multi_series_aggregator": "avg",
    },
    "go_goroutines": {
        "label": "Go goroutines",
        "category": "Application",
        "unit": "count",
        "aggregation": "avg",
        "higher_is_worse": True,
        "endpoint_scoped": True,
        "label_filter": "job",
        "multi_series_aggregator": "sum",
    },
    "go_threads": {
        "label": "Go OS threads",
        "category": "Application",
        "unit": "count",
        "aggregation": "avg",
        "higher_is_worse": True,
        "endpoint_scoped": True,
        "label_filter": "job",
        "multi_series_aggregator": "sum",
    },
    "go_sched_latencies_seconds_count": {
        "label": "Go scheduler events rate",
        "category": "Application",
        "unit": "count/s",
        "aggregation": "rate_avg",
        "higher_is_worse": False,
        "endpoint_scoped": True,
        "label_filter": "job",
        "multi_series_aggregator": "sum",
    },
    "go_sync_mutex_wait_total_seconds_total": {
        "label": "Go mutex wait time",
        "category": "Application",
        "unit": "seconds/s",
        "aggregation": "rate_avg",
        "higher_is_worse": True,
        "endpoint_scoped": True,
        "label_filter": "job",
        "multi_series_aggregator": "sum",
    },
    "go_sched_goroutines_runnable_goroutines": {
        "label": "Go runnable goroutines",
        "category": "Application",
        "unit": "count",
        "aggregation": "avg",
        "higher_is_worse": True,
        "endpoint_scoped": True,
        "label_filter": "job",
        "multi_series_aggregator": "sum",
    },
    "net_conntrack_listener_conn_accepted_total": {
        "label": "Conntrack listener accept rate",
        "category": "Application",
        "unit": "count/s",
        "aggregation": "rate_avg",
        "higher_is_worse": False,
        "endpoint_scoped": True,
        "label_filter": "job",
        "multi_series_aggregator": "sum",
    },
    "net_conntrack_dialer_conn_established_total": {
        "label": "Conntrack dialer established rate",
        "category": "Application",
        "unit": "count/s",
        "aggregation": "rate_avg",
        "higher_is_worse": False,
        "endpoint_scoped": True,
        "label_filter": "job",
        "multi_series_aggregator": "sum",
    },
    "net_conntrack_dialer_conn_failed_total": {
        "label": "Conntrack dialer failure rate",
        "category": "Application",
        "unit": "count/s",
        "aggregation": "rate_avg",
        "higher_is_worse": True,
        "endpoint_scoped": True,
        "label_filter": "job",
        "multi_series_aggregator": "sum",
    },
}


# Default metric set for single-cycle (threshold-based) analysis.
# Frontend can fetch this via GET /single-cycle-defaults to populate the
# threshold-input form when the user picks exactly one cycle.
SINGLE_CYCLE_DEFAULT_METRICS = [
    "probe_success",
    "probe_duration_seconds",
    "probe_http_duration_seconds",
    "probe_http_status_code",
    "probe_dns_lookup_time_seconds",
    "process_cpu_seconds_total",
    "process_resident_memory_bytes",
    "process_open_fds",
    "process_network_receive_bytes_total",
    "process_network_transmit_bytes_total",
    "process_start_time_seconds",
    "go_gc_duration_seconds",
    "go_gc_pauses_seconds_count",
    "go_gc_heap_allocs_bytes_total",
    "go_gc_heap_allocs_objects_total",
    "go_gc_heap_live_bytes",
    "go_gc_cycles_total_gc_cycles_total",
    "go_memstats_heap_inuse_bytes",
    "go_memstats_heap_alloc_bytes",
    "go_memstats_alloc_bytes_total",
    "go_memstats_stack_inuse_bytes",
    "go_memstats_next_gc_bytes",
    "go_goroutines",
    "go_threads",
    "go_sched_latencies_seconds_count",
    "go_sync_mutex_wait_total_seconds_total",
    "go_sched_goroutines_runnable_goroutines",
    "net_conntrack_listener_conn_accepted_total",
    "net_conntrack_dialer_conn_established_total",
    "net_conntrack_dialer_conn_failed_total",
]


# --------------------------------------------------------------------------- #
# Heuristic inference for everything not in CURATED_METRICS
# --------------------------------------------------------------------------- #

_BAD_KEYWORDS = (
    "error", "fail", "drop", "reject", "timeout",
    "oom", "crash", "evict", "throttl", "panic", "abort",
)
_GOOD_KEYWORDS = (
    "success", "available", "hit", "throughput",
    "ready", "alive", "healthy", "ok",
)


def _humanize(name: str) -> str:
    """metric_name_in_snake_case → 'Metric name in snake case'."""
    cleaned = name.replace("_total", "").replace("_seconds", "")
    parts = cleaned.split("_")
    return " ".join(parts).strip().capitalize() or name


def infer_metric_metadata(name: str) -> dict:
    """
    Best-effort metadata for a metric the catalog has no curated entry for.
    Uses Prometheus naming conventions; conservative defaults elsewhere.
    """
    n = name.lower()

    # Category + endpoint scoping
    if n.startswith("probe_"):
        category, scoped, label_filter = "Probing", True, "job"
    elif n.startswith("container_"):
        category, scoped, label_filter = (
            "Container",
            True,
            "container_label_com_docker_compose_service",
        )
    elif n.startswith("node_"):
        category, scoped, label_filter = "Host", False, None
    else:
        category, scoped, label_filter = "Custom", False, None

    # Aggregation: counters → rate then avg; everything else → avg
    is_counter = n.endswith("_total") or n.endswith("_count")
    aggregation = "rate_avg" if is_counter else "avg"

    # Unit
    if n.endswith("_bytes") or n.endswith("_bytes_total"):
        unit = "bytes/s" if is_counter else "bytes"
    elif n.endswith("_seconds") or n.endswith("_seconds_total"):
        unit = "seconds/s" if is_counter else "seconds"
    elif n.endswith("_celsius"):
        unit = "celsius"
    elif n.endswith("_ratio") or n.endswith("_percent"):
        unit = "ratio"
    elif is_counter:
        unit = "count/s"
    else:
        unit = "unknown"

    # Regression direction
    if any(k in n for k in _BAD_KEYWORDS):
        higher_is_worse = True
    elif any(k in n for k in _GOOD_KEYWORDS):
        higher_is_worse = False
    else:
        higher_is_worse = True  # conservative default

    # Multi-series rollup
    multi_series_aggregator = "sum" if aggregation == "rate_avg" else "avg"

    return {
        "label": _humanize(name),
        "category": category,
        "unit": unit,
        "aggregation": aggregation,
        "higher_is_worse": higher_is_worse,
        "endpoint_scoped": scoped,
        "label_filter": label_filter,
        "multi_series_aggregator": multi_series_aggregator,
    }


# --------------------------------------------------------------------------- #
# Catalog with per-app cache
# --------------------------------------------------------------------------- #

class MetricCatalog:
    def __init__(self):
        self._cache: Dict[int, Tuple[List[dict], float]] = {}

    async def get_for_app(self, application_id: int) -> List[dict]:
        now = time.time()
        cached = self._cache.get(application_id)
        if cached and now < cached[1]:
            return cached[0]

        vm_base = self._resolve_vm_base(application_id)
        names = await self._fetch_metric_names(vm_base)
        entries = self._build_catalog(names)

        self._cache[application_id] = (entries, now + settings.CATALOG_CACHE_TTL)
        return entries

    def invalidate(self, application_id: Optional[int] = None) -> None:
        if application_id is None:
            self._cache.clear()
        else:
            self._cache.pop(application_id, None)

    # -- internals -- #

    def _resolve_vm_base(self, application_id: int) -> str:
        """Look up the per-app VictoriaMetrics URL; strip the `/api/...` suffix."""
        supabase = get_supabase_client()
        result = (
            supabase.table("applications")
            .select("victoria_metrics_url")
            .eq("id", application_id)
            .limit(1)
            .execute()
        )
        if not result.data:
            raise ValueError(f"Application '{application_id}' not found")

        vm_url = result.data[0].get("victoria_metrics_url")
        if not vm_url:
            raise ValueError(
                f"Application '{application_id}' has no victoria_metrics_url configured"
            )

        # vm_url is typically "http://host:8428/api/v1/query".
        # We need the base "http://host:8428".
        return vm_url.split("/api/")[0].rstrip("/")

    async def _fetch_metric_names(self, vm_base: str) -> List[str]:
        url = f"{vm_base}/api/v1/label/__name__/values"
        try:
            async with httpx.AsyncClient(timeout=settings.VM_HTTP_TIMEOUT) as client:
                response = await client.get(url)
                response.raise_for_status()
                payload = response.json()
        except httpx.HTTPError as e:
            raise RuntimeError(f"Could not reach VictoriaMetrics at {url}: {e}") from e

        names = payload.get("data", [])
        if not isinstance(names, list):
            raise RuntimeError(f"Unexpected response from {url}: {payload}")

        logger.info(f"Discovered {len(names)} metrics from {vm_base}")
        return sorted(names)

    def _build_catalog(self, names: List[str]) -> List[dict]:
        entries = []
        for name in names:
            if name in CURATED_METRICS:
                meta = dict(CURATED_METRICS[name])
                meta["source"] = "curated"
            else:
                meta = infer_metric_metadata(name)
                meta["source"] = "inferred"
            meta["key"] = name
            entries.append(meta)
        return entries


catalog = MetricCatalog()
