import json
import asyncio
from typing import Dict, List, Callable, Optional
from aiokafka import AIOKafkaProducer, AIOKafkaConsumer
import structlog

from new_system.events.base import DomainEvent

logger = structlog.get_logger(__name__)

class KafkaEventBus:
    def __init__(self, bootstrap_servers: str, consumer_group_id: str = "accounting_service"):
        self.bootstrap_servers = bootstrap_servers
        self.producer: Optional[AIOKafkaProducer] = None
        self.consumer: Optional[AIOKafkaConsumer] = None
        self.handlers: Dict[str, List[Callable]] = {}
        self.consumer_group_id = consumer_group_id
        self._consumer_task: Optional[asyncio.Task] = None

    async def start(self):
        """Starts the Kafka producer and consumer."""
        self.producer = AIOKafkaProducer(
            bootstrap_servers=self.bootstrap_servers,
            value_serializer=lambda v: json.dumps(v, default=str).encode('utf-8')
        )
        await self.producer.start()
        logger.info("Kafka producer started.")

        if self.handlers:
            topics = [self._topic_name(event_type) for event_type in self.handlers.keys()]
            self.consumer = AIOKafkaConsumer(
                *topics,
                bootstrap_servers=self.bootstrap_servers,
                group_id=self.consumer_group_id,
                value_deserializer=lambda m: json.loads(m.decode('utf-8')),
                enable_auto_commit=False # For at-least-once processing
            )
            await self.consumer.start()
            self._consumer_task = asyncio.create_task(self._consume())
            logger.info("Kafka consumer started.", topics=topics, group_id=self.consumer_group_id)

    async def stop(self):
        """Stops the Kafka producer and consumer."""
        if self.producer:
            await self.producer.stop()
            logger.info("Kafka producer stopped.")
        if self._consumer_task:
            self._consumer_task.cancel()
        if self.consumer:
            await self.consumer.stop()
            logger.info("Kafka consumer stopped.")

    def _topic_name(self, event_type: str) -> str:
        """Generates a topic name from an event type."""
        return f"accounting.{event_type.lower()}"

    async def publish(self, event: DomainEvent):
        """Publishes a domain event to the corresponding Kafka topic."""
        if not self.producer:
            raise RuntimeError("Kafka producer is not started.")
            
        topic = self._topic_name(event.event_type)
        
        event_payload = {
            "event_id": str(event.event_id),
            "aggregate_id": str(event.aggregate_id),
            "event_type": event.event_type,
            "event_data": event.event_data,
            "version": event.version,
            "timestamp": event.timestamp.isoformat(),
            "metadata": event.metadata
        }
        
        await self.producer.send_and_wait(topic, event_payload)
        logger.info(
            "Event published to Kafka",
            event_type=event.event_type,
            aggregate_id=str(event.aggregate_id),
            topic=topic
        )

    def subscribe(self, event_type: str, handler: Callable):
        """Subscribes a handler to a specific event type."""
        if event_type not in self.handlers:
            self.handlers[event_type] = []
        self.handlers[event_type].append(handler)
        logger.info("Handler subscribed to event type", event_type=event_type, handler=handler.__name__)

    async def _consume(self):
        """The main loop for consuming messages from Kafka."""
        try:
            async for msg in self.consumer:
                try:
                    event_type = msg.value.get("event_type")
                    if event_type in self.handlers:
                        for handler in self.handlers[event_type]:
                            await handler(msg.value)
                    
                    # Commit the message offset after successful processing
                    await self.consumer.commit()
                except Exception as e:
                    logger.error(
                        "Event handling failed",
                        error=str(e),
                        topic=msg.topic,
                        partition=msg.partition,
                        offset=msg.offset,
                        exc_info=True
                    )
                    # In a real app, you'd have a dead-letter queue or other retry mechanism here.
        except asyncio.CancelledError:
            logger.info("Consumer task cancelled.")
        finally:
            logger.info("Consumer loop stopped.")
