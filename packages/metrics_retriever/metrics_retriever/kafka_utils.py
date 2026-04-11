import json
import logging
from confluent_kafka import Producer
from .config import settings

logger = logging.getLogger(__name__)

class KafkaManager:
    def __init__(self):
        conf = {
            'bootstrap.servers': settings.kafka_bootstrap_servers,
            'client.id': 'metrics-retriever-service',
            'linger.ms': 0,  # Send immediately for real-time
            'compression.type': 'snappy'
        }
        self.producer = Producer(conf)

    def delivery_report(self, err, msg):
        if err is not None:
            # We use msg.key() to know WHICH container's metrics failed
            logger.error(
                f"Delivery failed for {msg.key().decode('utf-8')}: {err}"
            )
        else:
            # Industry Standard: Low-level 'debug' or 'info' log for every 100th message
            # Or just a success log for visibility during development
            logger.info(
                f"Metrics delivered to {msg.topic()} "
                f"partition [{msg.partition()}] at offset {msg.offset()}"
            )

    def produce(self, key: str, data: dict):
        try:
            payload = json.dumps(data).encode('utf-8')
            self.producer.produce(
                settings.kafka_topic,
                key=key.encode('utf-8'),
                value=payload,
                callback=self.delivery_report
            )
            self.producer.poll(0)
        except Exception as e:
            logger.error(f"Kafka Produce Error: {e}")

    def flush(self):
        logger.info("Flushing Kafka producer...")
        self.producer.flush()

kafka_mgr = KafkaManager()