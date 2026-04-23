# import asyncio
# import time
# import httpx
# import logging
# from typing import List, Dict
# from .config import settings
# from .kafka_utils import kafka_mgr
# from .db_manager import RetrieverDBManager

# logger = logging.getLogger(__name__)

# class MetricsScraper:
#     def __init__(self):
#         self.is_running = True

#     def get_queries(self, c_name: str, p_name: str):
#         """
#         Returns the full set of PromQL queries.
#         We use a [2s] window ('win') because PromQL range functions 
#         (rate, avg_over_time, etc.) require at least two data points 
#         to calculate a value at a 1-second scraping interval.
#         """
#         win = "30s"
        
#         return {
#             # --- Probing & Latency Metrics ---
#             "latency_p95": f'quantile_over_time(0.95, probe_duration_seconds{{job="{p_name}"}}[{win}])',
#             "latency_std": f'stddev_over_time(probe_duration_seconds{{job="{p_name}"}}[{win}])',
#             "error_rate": f'1 - avg_over_time(probe_success{{job="{p_name}"}}[{win}])',

#             # --- Container Performance Metrics ---
#             "cpu_usage_rate": f'rate(container_cpu_usage_seconds_total{{container_label_com_docker_compose_service="{c_name}"}}[{win}])',
#             "memory_usage_avg": f'avg_over_time(container_memory_usage_bytes{{container_label_com_docker_compose_service="{c_name}"}}[{win}])',
#             "net_throughput": (
#                 f'rate(container_network_receive_bytes_total{{container_label_com_docker_compose_service="{c_name}"}}[{win}]) + '
#                 f'rate(container_network_transmit_bytes_total{{container_label_com_docker_compose_service="{c_name}"}}[{win}])'
#             ),

#             # --- Node & System Metrics ---
#             "disk_io_rate": f'sum(rate(node_disk_io_time_seconds_total[{win}]))',
#             "node_cpu_total": f'sum(rate(node_cpu_seconds_total[{win}]))',
#             "node_memory_MemAvailable_bytes": 'node_memory_MemAvailable_bytes',

#             # --- Instant/Raw Metrics (No window needed) ---
#             "container_memory_usage_bytes": f'container_memory_usage_bytes{{container_label_com_docker_compose_service="{c_name}"}}',
#             "container_start_time_seconds": f'container_start_time_seconds{{container_label_com_docker_compose_service="{c_name}"}}',
#             "probe_success": f'probe_success{{job="{p_name}"}}'
#         }

#     async def fetch_metric(self, client: httpx.AsyncClient, name: str, query: str):
#         """Fetches a single metric from VictoriaMetrics with error handling."""
#         try:
#             # We use a tight timeout (800ms) to ensure we don't lag the 1s loop
#             resp = await client.get(settings.vm_url, params={"query": query}, timeout=0.8)
#             resp.raise_for_status()
            
#             data = resp.json()
#             results = data.get("data", {}).get("result", [])
            
#             # VictoriaMetrics returns values as [timestamp, "value"]
#             if results and "value" in results[0]:
#                 val = results[0]["value"][1]
#                 return name, float(val)
            
#             return name, 0.0
#         except Exception as e:
#             # Log as warning to keep the console clean but track failures
#             logger.warning(f"Fetch failed for {name}: {e}")
#             return name, 0.0

#     async def process_single_job(self, client: httpx.AsyncClient, job: Dict):
#         """
#         Handles the full scraping cycle for ONE application/config.
#         """
#         c_name = job['container_name']
#         p_name = job['probe_name']
        
#         # 1. Fetch all 12 queries concurrently for this specific job
#         queries = self.get_queries(c_name, p_name)
#         tasks = [self.fetch_metric(client, name, q) for name, q in queries.items()]
#         results = await asyncio.gather(*tasks)
        
#         # 2. Build the Identity-Aware Payload
#         metrics_payload = {name: val for name, val in results}
        
#         full_payload = {
#             "application_id": job['application_id'],
#             "config_id": job['config_id'],
#             "endpoint_id": job['endpoint_id'],
#             "timestamp": time.time(),
#             "container_name": c_name,
#             "probe_name": p_name,
#             "metrics": metrics_payload
#         }

#         # 3. Push to Kafka using application_id as key for ordering
#         kafka_mgr.produce(key=str(job['application_id']), data=full_payload)

import asyncio
import time
import httpx
import logging
from typing import List, Dict, Optional, Tuple
from .config import settings
from .kafka_utils import kafka_mgr
from .db_manager import RetrieverDBManager

logger = logging.getLogger(__name__)

class MetricsScraper:
    def __init__(self):
        self.is_running = True

    def get_queries(self, c_name: str, p_name: str):
        # Increased window to 30s as discussed for stability
        win = "30s"
        
        return {
            "latency_p95": f'quantile_over_time(0.95, probe_duration_seconds{{job="{p_name}"}}[{win}])',
            "latency_std": f'stddev_over_time(probe_duration_seconds{{job="{p_name}"}}[{win}])',
            "error_rate": f'1 - avg_over_time(probe_success{{job="{p_name}"}}[{win}])',
            "cpu_usage_rate": f'rate(container_cpu_usage_seconds_total{{container_label_com_docker_compose_service="{c_name}"}}[{win}])',
            "memory_usage_avg": f'avg_over_time(container_memory_usage_bytes{{container_label_com_docker_compose_service="{c_name}"}}[{win}])',
            "net_throughput": (
                f'sum(rate(container_network_receive_bytes_total{{container_label_com_docker_compose_service="{c_name}"}}[{win}])) + '
                f'sum(rate(container_network_transmit_bytes_total{{container_label_com_docker_compose_service="{c_name}"}}[{win}]))'
            ),
            "disk_io_rate": f'sum(rate(node_disk_io_time_seconds_total[{win}]))',
            # Added mode!="idle" to ensure we get actual usage, not total cores
            "node_cpu_total": f'sum(rate(node_cpu_seconds_total{{mode!="idle"}}[{win}]))',
            "node_memory_MemAvailable_bytes": 'node_memory_MemAvailable_bytes',
            "container_memory_usage_bytes": f'container_memory_usage_bytes{{container_label_com_docker_compose_service="{c_name}"}}',
            "container_start_time_seconds": f'container_start_time_seconds{{container_label_com_docker_compose_service="{c_name}"}}',
            "probe_success": f'probe_success{{job="{p_name}"}}'
        }

    async def fetch_metric(self, client: httpx.AsyncClient, name: str, query: str) -> Tuple[str, Optional[float]]:
        """Fetches a single metric. Returns None on failure instead of 0.0."""
        try:
            # INCREASED TIMEOUT: 0.8s was too tight for complex PromQL quantiles.
            # 1.5s gives the DB enough time to calculate the 30s window.
            resp = await client.get(settings.vm_url, params={"query": query}, timeout=1.5)
            resp.raise_for_status()
            
            data = resp.json()
            results = data.get("data", {}).get("result", [])
            
            if results and "value" in results[0]:
                val = results[0]["value"][1]
                return name, float(val)
            
            # CRITICAL CHANGE: Return None, not 0.0. 
            # This allows us to detect a "No Data" scenario.
            return name, None
        except Exception as e:
            logger.debug(f"Fetch failed for {name}: {e}")
            return name, None

    async def process_single_job(self, client: httpx.AsyncClient, job: Dict):
        c_name = job['container_name']
        p_name = job['probe_name']
        
        queries = self.get_queries(c_name, p_name)
        tasks = [self.fetch_metric(client, name, q) for name, q in queries.items()]
        results = await asyncio.gather(*tasks)
        
        # 1. Check for "None" values (Missing Metrics)
        metrics_payload = {}
        missing_count = 0
        for name, val in results:
            if val is None:
                missing_count += 1
            else:
                metrics_payload[name] = val

        # 2. VALIDATION: If more than 3 metrics are missing, the scrape is unreliable.
        # We discard the entire payload rather than training the ML model on half-data.
        if missing_count > 3:
            logger.warning(f"Discarding payload for {c_name}: {missing_count} metrics missing.")
            return

        full_payload = {
            "application_id": job['application_id'],
            "config_id": job['config_id'],
            "endpoint_id": job['endpoint_id'],
            "timestamp": time.time(),
            "container_name": c_name,
            "probe_name": p_name,
            "metrics": metrics_payload
        }

        kafka_mgr.produce(key=str(job['application_id']), data=full_payload)

    async def run_scrape_batch(self, active_jobs: List[Dict]):
        """
        The entry point called by main.py every second.
        Processes all active jobs in parallel.
        """
        if not active_jobs:
            return

        async with httpx.AsyncClient(limits=httpx.Limits(max_keepalive_connections=50)) as client:
            # Fire off processing for all applications at once
            job_tasks = [self.process_single_job(client, job) for job in active_jobs]
            await asyncio.gather(*job_tasks)

    def stop(self):
        """Graceful shutdown trigger."""
        self.is_running = False

# --- Add this at the very bottom of scraper.py ---

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    
    async def run_real_test():
        logger.info("Initializing Real-World Test...")
        db_manager = RetrieverDBManager(settings.database_url)
        scraper = MetricsScraper()
        
        try:
            while scraper.is_running:
                start_cycle = time.perf_counter()
                
                # 1. Fetch real jobs from Supabase
                logger.info("Fetching active jobs from Supabase...")
                jobs = await db_manager.get_active_monitoring_jobs()
                
                # 2. Run the scrape batch
                if jobs:
                    logger.info(f"Scraping {len(jobs)} active targets...")
                    await scraper.run_scrape_batch(jobs)
                
                # 3. Maintain 1s interval
                elapsed = time.perf_counter() - start_cycle
                await asyncio.sleep(max(0, 1.0 - elapsed))
                
        except KeyboardInterrupt:
            logger.info("Test stopped by user.")
        finally:
            await db_manager.close()
            kafka_mgr.flush()

    asyncio.run(run_real_test())