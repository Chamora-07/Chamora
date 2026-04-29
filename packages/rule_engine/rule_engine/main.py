import asyncio
import json
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("rule-engine")

from .judge import SlidingWindowJudge
from .db_manager import RuleDBManager
from .kafka_utils import consumer

async def start_engine():
    judge = SlidingWindowJudge()
    db = RuleDBManager()
    
    logger.info("Rule Engine Online. Listening for 'processed_features'...")

    try:
        while True:
            msg = consumer.poll(1.0)
            
            if msg is None:
                continue
            if msg.error():
                logger.error(f"Kafka error: {msg.error()}")
                continue

            try:
                data = json.loads(msg.value().decode('utf-8'))
                
                application_id = data.get("application_id")
                endpoint_id = data.get("endpoint_id")
                config_id = data.get("config_id")

                # ✅ Validate all three required fields
                if not application_id or not endpoint_id or not config_id:
                    logger.warning(
                        f"Packet missing required fields. "
                        f"application_id={application_id}, "
                        f"endpoint_id={endpoint_id}, "
                        f"config_id={config_id}. Skipping."
                    )
                    continue

                # Fetch config by endpoint_id
                cfg = await db.get_config(endpoint_id)
                if not cfg:
                    logger.warning(f"No active config for endpoint_id={endpoint_id}. Skipping.")
                    continue
                
                if not cfg.is_active:
                    continue

                # ✅ Window buffer keyed by config_id — isolates each endpoint
                verdict = judge.evaluate(config_id, data, cfg)

                if verdict:
                    await db.save_anomaly(verdict)
                    
                    status_icon = "🔴" if verdict['severity'] == "CRITICAL" else "🟡"
                    logger.warning(
                        f"{status_icon} {verdict['severity']} DETECTED | "
                        f"App: {application_id} | "
                        f"Config: {config_id} | "
                        f"Endpoint: {endpoint_id} | "
                        f"Cause: {verdict['root_cause']} | "
                        f"Score: {verdict['score']}"
                    )

            except json.JSONDecodeError:
                logger.error("Failed to decode Kafka message as JSON.")
            except Exception as e:
                logger.exception(f"Unexpected error processing message: {e}")

    except KeyboardInterrupt:
        logger.info("Rule Engine shutting down gracefully...")
    finally:
        consumer.close()
        logger.info("Kafka consumer closed.")

if __name__ == "__main__":
    try:
        asyncio.run(start_engine())
    except KeyboardInterrupt:
        pass