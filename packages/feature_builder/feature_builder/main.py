import asyncio
import json
import logging
import signal
from .transformer import FeatureTransformer
from .kafka_utils import kafka_mgr

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("FEATURE_BUILDER")

async def start_worker():
    transformer = FeatureTransformer()
    logger.info("Feature Builder initialized and waiting for raw_metrics...")

    try:
        while True:
            # 1. Poll Kafka for new raw metrics
            msg = kafka_mgr.consumer.poll(1.0)
            
            if msg is None:
                continue
            if msg.error():
                logger.error(f"Consumer error: {msg.error()}")
                continue

            # 2. Parse the raw JSON
            try:
                raw_payload = json.loads(msg.value().decode('utf-8'))
                
                # 3. Transform into 12 features
                enriched_data = transformer.transform(raw_payload)
                
                # 4. Push to processed_features topic
                kafka_mgr.produce(
                    key=enriched_data["application_id"], 
                    data=enriched_data
                )
                
                # logger.info(f"Processed App {enriched_data['application_id']}")
                
            except Exception as e:
                logger.error(f"Failed to process message: {e}")

    except KeyboardInterrupt:
        logger.info("Shutting down Feature Builder...")
    finally:
        kafka_mgr.consumer.close()
        kafka_mgr.flush()

if __name__ == "__main__":
    asyncio.run(start_worker())