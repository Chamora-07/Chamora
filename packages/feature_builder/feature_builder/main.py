import asyncio
import json
import logging
from .transformer import FeatureTransformer
from .kafka_utils import kafka_mgr

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("FEATURE_BUILDER")

async def start_worker():
    transformer = FeatureTransformer()
    logger.info("Feature Builder initialized and waiting for raw_metrics...")

    try:
        while True:
            msg = kafka_mgr.consumer.poll(1.0)
            
            if msg is None:
                continue
            if msg.error():
                logger.error(f"Consumer error: {msg.error()}")
                continue

            try:
                raw_payload = json.loads(msg.value().decode('utf-8'))

                # ✅ Validate required fields before processing
                application_id = raw_payload.get("application_id")
                config_id = raw_payload.get("config_id")
                endpoint_id = raw_payload.get("endpoint_id")

                if not application_id or not config_id or not endpoint_id:
                    logger.warning(
                        f"Dropping message — missing required fields. "
                        f"application_id={application_id}, "
                        f"config_id={config_id}, "
                        f"endpoint_id={endpoint_id}"
                    )
                    continue

                # Transform into 12 features
                enriched_data = transformer.transform(raw_payload)

                # ✅ Key by config_id so each config is isolated in its own partition
                kafka_mgr.produce(
                    key=str(enriched_data["config_id"]),
                    data=enriched_data
                )

            except json.JSONDecodeError:
                logger.error("Failed to decode Kafka message as JSON.")
            except Exception as e:
                logger.error(f"Failed to process message: {e}")

    except KeyboardInterrupt:
        logger.info("Shutting down Feature Builder...")
    finally:
        kafka_mgr.consumer.close()
        kafka_mgr.flush()

if __name__ == "__main__":
    asyncio.run(start_worker())