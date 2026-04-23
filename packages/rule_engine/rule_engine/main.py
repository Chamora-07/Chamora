import asyncio
import json
import logging
import sys

# 1. Fix the Logger: Initialize so output actually appears in your console/Docker logs
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("rule-engine")

# Internal Imports
from .judge import SlidingWindowJudge
from .db_manager import RuleDBManager
from .kafka_utils import consumer

async def start_engine():
    # Initialize our Brain and our Database Connection
    judge = SlidingWindowJudge()
    db = RuleDBManager()
    
    logger.info("Rule Engine Online. Listening for 'processed_features'...")

    try:
        while True:
            # Poll Kafka for new processed feature packets
            msg = consumer.poll(1.0)
            
            if msg is None:
                continue
            if msg.error():
                logger.error(f"Kafka error: {msg.error()}")
                continue

            try:
                # Parse the Kafka message
                data = json.loads(msg.value().decode('utf-8'))
                app_id = data.get("application_id")
                
                if not app_id:
                    logger.warning("Received packet without application_id. Skipping.")
                    continue

                # 1. Fetch live thresholds (Uses the 60s cache in db_manager)
                cfg = await db.get_config(app_id)
                if not cfg:
                    # If there's no config, we don't know the rules for this app
                    continue
                
                if not cfg.is_active:
                    continue

                # 2. Windowed Evaluation (The 3-point rolling window logic)
                # This uses all 12 features and calculates means
                verdict = judge.evaluate(app_id, data, cfg)

                # 3. Persistence Filter: Only save WARNING or CRITICAL
                # judge.evaluate returns None for 'NORMAL' states
                if verdict:
                    # verdict now contains the window_timestamp (T2) and 12-feature evidence
                    await db.save_anomaly(verdict)
                    
                    # Log the finding to console
                    status_icon = "🔴" if verdict['severity'] == "CRITICAL" else "🟡"
                    logger.warning(
                        f"{status_icon} {verdict['severity']} DETECTED | "
                        f"App: {app_id} | Cause: {verdict['root_cause']} | "
                        f"Score: {verdict['score']}"
                    )

            except json.JSONDecodeError:
                logger.error("Failed to decode Kafka message as JSON.")
            except Exception as e:
                logger.exception(f"Unexpected error in main loop: {e}")

    except KeyboardInterrupt:
        logger.info("Rule Engine shutting down gracefully...")
    finally:
        # Important: Close Kafka connection to avoid re-balancing issues
        consumer.close()
        logger.info("Kafka consumer closed.")

if __name__ == "__main__":
    try:
        asyncio.run(start_engine())
    except KeyboardInterrupt:
        pass