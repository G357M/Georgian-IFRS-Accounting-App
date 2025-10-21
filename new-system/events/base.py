from dataclasses import dataclass, field
from typing import Any, List, Dict
from abc import ABC, abstractmethod
import uuid
from datetime import datetime

@dataclass(frozen=True)
class DomainEvent:
    """Base class for domain events."""
    aggregate_id: uuid.UUID
    event_type: str
    event_data: Dict[str, Any]
    version: int
    event_id: uuid.UUID = field(default_factory=uuid.uuid4)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)

class Aggregate(ABC):
    """Base class for aggregates in the event sourcing model."""
    
    def __init__(self, aggregate_id: uuid.UUID):
        self.id = aggregate_id
        self.version = 0
        self.uncommitted_events: List[DomainEvent] = []
    
    def _apply_event(self, event: DomainEvent):
        """Applies an event to the aggregate's state."""
        # The method name is constructed from the event type, e.g., "TransactionCreated" -> _on_transaction_created
        handler_name = f"_on_{event.event_type.lower()}"
        handler = getattr(self, handler_name, None)
        if handler:
            handler(event)
        
        if event.version > self.version:
            self.version = event.version
            
    def raise_event(self, event_type: str, event_data: Dict[str, Any], metadata: Dict[str, Any] = None):
        """Creates a new domain event and applies it to the aggregate."""
        event = DomainEvent(
            aggregate_id=self.id,
            event_type=event_type,
            event_data=event_data,
            version=self.version + 1,
            metadata=metadata or {}
        )
        self._apply_event(event)
        self.uncommitted_events.append(event)
    
    def mark_events_as_committed(self):
        """Clears the list of uncommitted events."""
        self.uncommitted_events.clear()

    @classmethod
    def replay_events(cls, aggregate_id: uuid.UUID, events: List[DomainEvent]) -> 'Aggregate':
        """Reconstructs an aggregate from a history of events."""
        aggregate = cls(aggregate_id)
        for event in events:
            aggregate._apply_event(event)
        return aggregate
