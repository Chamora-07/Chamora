from fastapi import APIRouter
import asyncio
import logging
from .scraper import MetricsScraper
from .db_manager import RetrieverDBManager
from .kafka_utils import kafka_mgr
from .config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/retriever", tags=["Metrics Retriever"])

class RetrieverManager:
    def __init__(self):
        self.scraper = MetricsScraper()
        self.db_manager = None
        self.active_jobs = []
        self._observer_task = None
        self._heartbeat_task = None
        self.is_running = False

    async def start(self):
        logger.info("Starting Metrics Retriever Engine...")
        self.db_manager = RetrieverDBManager(settings.database_url)
        self.is_running = True
        self._observer_task = asyncio.create_task(self._observer_loop())
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

    async def _observer_loop(self):
        """Background task to keep our job list in sync with the DB every 60s."""
        while self.is_running:
            try:
                jobs = await self.db_manager.get_active_monitoring_jobs()
                self.active_jobs = jobs
                logger.info(f"Retriever synced: Monitoring {len(self.active_jobs)} endpoints.")
            except Exception as e:
                logger.error(f"Observer loop error: {e}")
            await asyncio.sleep(60)

    async def _heartbeat_loop(self):
        """The actual scraping heartbeat — runs every 1 second."""
        while self.is_running:
            start_time = asyncio.get_event_loop().time()
            try:
                if self.active_jobs:
                    await self.scraper.run_scrape_batch(self.active_jobs)
            except Exception as e:
                logger.error(f"Scrape cycle error: {e}")
            elapsed = asyncio.get_event_loop().time() - start_time
            await asyncio.sleep(max(0, 1.0 - elapsed))

    async def refresh_jobs(self):
        """
        Called externally (e.g. from anomaly config API) when a user
        creates, updates, or deletes a config — so scraping starts instantly
        without waiting for the 60s observer cycle.
        """
        try:
            jobs = await self.db_manager.get_active_monitoring_jobs()
            self.active_jobs = jobs
            logger.info(f"Job list refreshed on-demand: {len(self.active_jobs)} endpoints.")
        except Exception as e:
            logger.error(f"On-demand refresh failed: {e}")

    async def stop(self):
        logger.info("Stopping Metrics Retriever background tasks...")
        self.is_running = False
        if self._observer_task:
            self._observer_task.cancel()
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
        if self.db_manager:
            await self.db_manager.close()
        kafka_mgr.flush()
        logger.info("Retriever shutdown complete.")

# Singleton manager
manager = RetrieverManager()

@router.get("/status")
async def get_status():
    return {
        "component": "metrics-retriever",
        "is_active": manager.is_running,
        "monitoring_count": len(manager.active_jobs),
        "active_endpoints": [
            {
                "app_id": j['application_id'],
                "config_id": j['config_id'],      # ← add this
                "endpoint_id": j['endpoint_id'],  # ← add this
                "container": j['container_name'],
                "probe": j['probe_name']           # ← add this
            }
            for j in manager.active_jobs
        ]
    }