from fastapi import APIRouter
import asyncio
import logging
from .scraper import MetricsScraper
from .db_manager import RetrieverDBManager  # The new eye
from .kafka_utils import kafka_mgr
from .config import settings  # Ensure your settings have database_url and vm_url

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
        """Initializes components and kicks off the background loops."""
        logger.info("Starting Metrics Retriever Engine...")
        
        self.db_manager = RetrieverDBManager(settings.database_url)
        self.is_running = True

        # 1. Start the Observer Loop (Sync with Supabase every 60s)
        self._observer_task = asyncio.create_task(self._observer_loop())
        
        # 2. Start the Heartbeat Loop (The 1-second scraping cycle)
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

    async def _observer_loop(self):
        """Background task to keep our job list in sync with the DB."""
        while self.is_running:
            try:
                # Poll Supabase for active apps/endpoints
                jobs = await self.db_manager.get_active_monitoring_jobs()
                self.active_jobs = jobs
                logger.info(f"Retriever synced: Monitoring {len(self.active_jobs)} endpoints.")
            except Exception as e:
                logger.error(f"Observer loop error: {e}")
            
            await asyncio.sleep(60) # Refresh every minute

    async def _heartbeat_loop(self):
        """The actual scraping heartbeat."""
        while self.is_running:
            start_time = asyncio.get_event_loop().time()
            
            try:
                if self.active_jobs:
                    # Batch process all 12 metrics for all active jobs
                    await self.scraper.run_scrape_batch(self.active_jobs)
            except Exception as e:
                logger.error(f"Scrape cycle error: {e}")

            # Calculate sleep to maintain a steady 1.0s rhythm
            elapsed = asyncio.get_event_loop().time() - start_time
            await asyncio.sleep(max(0, 1.0 - elapsed))

    async def stop(self):
        """Graceful shutdown sequence."""
        logger.info("Stopping Metrics Retriever background tasks...")
        self.is_running = False
        
        # Cancel the loops
        if self._observer_task:
            self._observer_task.cancel()
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            
        # Clean up database connections
        if self.db_manager:
            await self.db_manager.close()
            
        kafka_mgr.flush()
        logger.info("Retriever shutdown complete.")

# Singleton manager
manager = RetrieverManager()

@router.get("/status")
async def get_status():
    """Returns the live status of the monitoring engine."""
    return {
        "component": "metrics-retriever",
        "is_active": manager.is_running,
        "monitoring_count": len(manager.active_jobs),
        "active_endpoints": [
            {"app_id": j['application_id'], "container": j['container_name']} 
            for j in manager.active_jobs
        ]
    }