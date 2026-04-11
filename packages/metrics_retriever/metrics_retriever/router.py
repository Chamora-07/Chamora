from fastapi import APIRouter
import asyncio
import logging
from .scraper import MetricsScraper
from .kafka_utils import kafka_mgr

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/retriever", tags=["Metrics Retriever"])

# This manages the lifecycle of this specific component
class RetrieverManager:
    def __init__(self):
        self.scraper = MetricsScraper()
        self.task = None

    async def start(self):
        logger.info("Starting Metrics Retriever background task...")
        self.task = asyncio.create_task(self.scraper.run_loop())

    async def stop(self):
        logger.info("Stopping Metrics Retriever...")
        self.scraper.stop()
        if self.task:
            await self.task
        kafka_mgr.flush()

# Create a singleton manager
manager = RetrieverManager()

@router.get("/status")
async def get_status():
    return {
        "component": "metrics-retriever",
        "active": manager.scraper.is_running,
        "target": manager.scraper.c_name
    }