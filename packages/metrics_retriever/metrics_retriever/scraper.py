import asyncio
import time
import httpx
import logging
from .config import settings
from .kafka_utils import kafka_mgr

logger = logging.getLogger(__name__)

class MetricsScraper:
    def __init__(self):
        self.is_running = True
        # Using aliases from settings for readability
        self.c_name = settings.target_container_name
        self.p_name = settings.target_probe_name

    def get_queries(self):
        """
        Returns the full set of PromQL queries.
        We use a [2s] window ('win') because PromQL range functions 
        (rate, avg_over_time, etc.) require at least two data points 
        to calculate a value at a 1-second scraping interval.
        """
        win = "2s"
        
        return {
            # --- Probing & Latency Metrics ---
            "latency_p95": f'quantile_over_time(0.95, probe_duration_seconds{{job="{self.p_name}"}}[{win}])',
            "latency_std": f'stddev_over_time(probe_duration_seconds{{job="{self.p_name}"}}[{win}])',
            "error_rate": f'1 - avg_over_time(probe_success{{job="{self.p_name}"}}[{win}])',

            # --- Container Performance Metrics ---
            "cpu_usage_rate": f'rate(container_cpu_usage_seconds_total{{container_label_com_docker_compose_service="{self.c_name}"}}[{win}])',
            "memory_usage_avg": f'avg_over_time(container_memory_usage_bytes{{container_label_com_docker_compose_service="{self.c_name}"}}[{win}])',
            "net_throughput": (
                f'rate(container_network_receive_bytes_total{{container_label_com_docker_compose_service="{self.c_name}"}}[{win}]) + '
                f'rate(container_network_transmit_bytes_total{{container_label_com_docker_compose_service="{self.c_name}"}}[{win}])'
            ),

            # --- Node & System Metrics ---
            "disk_io_rate": f'rate(node_disk_io_time_seconds_total[{win}])',
            "node_cpu_total": f'rate(node_cpu_seconds_total[{win}])',
            "node_memory_MemAvailable_bytes": 'node_memory_MemAvailable_bytes',

            # --- Instant/Raw Metrics (No window needed) ---
            "container_memory_usage_bytes": f'container_memory_usage_bytes{{container_label_com_docker_compose_service="{self.c_name}"}}',
            "container_start_time_seconds": f'container_start_time_seconds{{container_label_com_docker_compose_service="{self.c_name}"}}',
            "probe_success": f'probe_success{{job="{self.p_name}"}}'
        }

    async def fetch_metric(self, client: httpx.AsyncClient, name: str, query: str):
        """Fetches a single metric from VictoriaMetrics with error handling."""
        try:
            # We use a tight timeout (800ms) to ensure we don't lag the 1s loop
            resp = await client.get(settings.vm_url, params={"query": query}, timeout=0.8)
            resp.raise_for_status()
            
            data = resp.json()
            results = data.get("data", {}).get("result", [])
            
            # VictoriaMetrics returns values as [timestamp, "value"]
            if results and "value" in results[0]:
                val = results[0]["value"][1]
                return name, float(val)
            
            return name, 0.0
        except Exception as e:
            # Log as warning to keep the console clean but track failures
            logger.warning(f"Fetch failed for {name}: {e}")
            return name, 0.0

    async def run_loop(self):
        """The main 24/7 execution loop."""
        logger.info(f"Starting Scraper: Targeting {self.c_name} every {settings.scraping_interval}s")
        
        # httpx.AsyncClient is placed outside the loop for Connection Pooling
        async with httpx.AsyncClient(limits=httpx.Limits(max_keepalive_connections=15)) as client:
            while self.is_running:
                start_cycle = time.perf_counter()
                
                # 1. Fetch all 12 queries concurrently using asyncio.gather
                queries = self.get_queries()
                tasks = [self.fetch_metric(client, name, q) for name, q in queries.items()]
                results = await asyncio.gather(*tasks)
                
                # 2. Build the JSON Payload
                payload = {name: val for name, val in results}
                payload["timestamp"] = time.time()
                payload["container_name"] = self.c_name

                # 3. Push to Kafka Conveyor Belt
                # Using container name as the Kafka key ensures ordered processing
                kafka_mgr.produce(key=self.c_name, data=payload)

                # 4. Drift-Corrected Sleep
                # Ensures we trigger the next fetch at exactly 1.0s intervals
                elapsed = time.perf_counter() - start_cycle
                sleep_duration = max(0, settings.scraping_interval - elapsed)
                
                if elapsed > settings.scraping_interval:
                    logger.warning(f"Scrape cycle took {elapsed:.2f}s - resolution may be degraded")
                
                await asyncio.sleep(sleep_duration)

    def stop(self):
        """Graceful shutdown trigger."""
        self.is_running = False