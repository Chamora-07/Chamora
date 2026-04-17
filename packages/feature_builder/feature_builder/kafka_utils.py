import json
import logging
from confluent_kafka import Producer, Consumer
from .config import settings

logger = logging.getLogger(__name__)

class FeatureKafkaManager:
    def __init__(self):
        # Producer Config (Same as Retriever)
        p_conf = {
            'bootstrap.servers': settings.kafka_bootstrap_servers,
            'client.id': 'feature-builder-producer',
            'linger.ms': 10
        }
        self.producer = Producer(p_conf)

        # Consumer Config
        c_conf = {
            'bootstrap.servers': settings.kafka_bootstrap_servers,
            'group.id': 'feature-builder-group',
            'auto.offset.reset': 'earliest'
        }
        self.consumer = Consumer(c_conf)
        self.consumer.subscribe([settings.source_topic])

    def produce(self, key: str, data: dict):
        try:
            self.producer.produce(
                settings.sink_topic,
                key=str(key).encode('utf-8'),
                value=json.dumps(data).encode('utf-8')
            )
            self.producer.poll(0)
        except Exception as e:
            logger.error(f"Kafka Production Error: {e}")

    def flush(self):
        self.producer.flush()

kafka_mgr = FeatureKafkaManager()