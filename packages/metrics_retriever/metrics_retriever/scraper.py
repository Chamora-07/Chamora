import asyncio
import time
import httpx
import logging
from typing import List, Dict, Optional, Tuple
from .kafka_utils import kafka_mgr
from .db_manager import RetrieverDBManager
from .config import settings

logger = logging.getLogger(__name__)

class MetricsScraper:
    def __init__(self):
        self.is_running = True

    def get_queries(self, c_name: str, p_name: str):
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
            "node_cpu_total": f'sum(rate(node_cpu_seconds_total{{mode!="idle"}}[{win}]))',
            "node_memory_MemAvailable_bytes": 'node_memory_MemAvailable_bytes',
            "container_memory_usage_bytes": f'container_memory_usage_bytes{{container_label_com_docker_compose_service="{c_name}"}}',
            "container_start_time_seconds": f'container_start_time_seconds{{container_label_com_docker_compose_service="{c_name}"}}',
            "probe_success": f'probe_success{{job="{p_name}"}}'
        }

    async def fetch_metric(
        self,
        client: httpx.AsyncClient,
        vm_url: str,
        name: str,
        query: str
    ) -> Tuple[str, Optional[float]]:
        """Fetches a single metric from the job-specific VictoriaMetrics instance."""
        try:
            resp = await client.get(vm_url, params={"query": query}, timeout=1.5)
            resp.raise_for_status()
            
            data = resp.json()
            results = data.get("data", {}).get("result", [])
            
            if results and "value" in results[0]:
                val = results[0]["value"][1]
                return name, float(val)
            
            return name, None
        except Exception as e:
            logger.debug(f"Fetch failed for {name} @ {vm_url}: {e}")
            return name, None

    async def process_single_job(self, client: httpx.AsyncClient, job: Dict):
        c_name = job['container_name']
        p_name = job['probe_name']
        vm_url = job['victoria_metrics_url']

        if not vm_url:
            logger.error(f"No victoria_metrics_url for app_id={job['application_id']}. Skipping.")
            return

        queries = self.get_queries(c_name, p_name)
        tasks = [self.fetch_metric(client, vm_url, name, q) for name, q in queries.items()]
        results = await asyncio.gather(*tasks)
        
        metrics_payload = {}
        missing_count = 0
        for name, val in results:
            if val is None:
                missing_count += 1
            else:
                metrics_payload[name] = val

        if missing_count > 3:
            logger.warning(
                f"Discarding payload for {c_name} (config_id={job['config_id']}): "
                f"{missing_count} metrics missing from {vm_url}."
            )
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

        kafka_mgr.produce(key=str(job['config_id']), data=full_payload)

    async def run_scrape_batch(self, active_jobs: List[Dict]):
        """
        Processes all active jobs in parallel.
        Each job hits its own application-specific VictoriaMetrics URL.
        """
        if not active_jobs:
            return

        async with httpx.AsyncClient(limits=httpx.Limits(max_keepalive_connections=50)) as client:
            job_tasks = [self.process_single_job(client, job) for job in active_jobs]
            await asyncio.gather(*job_tasks)

    def stop(self):
        self.is_running = False


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    
    async def run_real_test():
        logger.info("Initializing Real-World Test...")
        db_manager = RetrieverDBManager(settings.database_url)
        scraper = MetricsScraper()
        
        try:
            while scraper.is_running:
                start_cycle = time.perf_counter()
                
                logger.info("Fetching active jobs from Supabase...")
                jobs = await db_manager.get_active_monitoring_jobs()
                
                if jobs:
                    logger.info(f"Scraping {len(jobs)} active targets...")
                    await scraper.run_scrape_batch(jobs)
                
                elapsed = time.perf_counter() - start_cycle
                await asyncio.sleep(max(0, 1.0 - elapsed))
                
        except KeyboardInterrupt:
            logger.info("Test stopped by user.")
        finally:
            await db_manager.close()
            kafka_mgr.flush()

    asyncio.run(run_real_test())