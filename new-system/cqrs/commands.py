import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import List, Any
from abc import ABC, abstractmethod

from new_system.domain.aggregates import AccountingTransaction, JournalEntryData

# --- Placeholder interfaces for infrastructure ---
class IEventStore(ABC):
    @abstractmethod
    async def save_events(self, aggregate_id: uuid.UUID, events: List[Any], expected_version: int):
        pass

class IEventBus(ABC):
    @abstractmethod
    async def publish(self, event: Any):
        pass

# --- Base Command Classes ---
class Command(ABC):
    """Base class for commands."""
    pass

class CommandHandler(ABC):
    @abstractmethod
    async def handle(self, command: Command) -> Any:
        pass

# --- CreateTransaction Command ---
@dataclass
class CreateTransactionCommand(Command):
    transaction_date: datetime
    description: str
    entries: List[JournalEntryData]
    created_by: uuid.UUID

class CreateTransactionHandler(CommandHandler):
    def __init__(self, event_store: IEventStore, event_bus: IEventBus):
        self.event_store = event_store
        self.event_bus = event_bus
    
    async def handle(self, command: CreateTransactionCommand) -> uuid.UUID:
        transaction_id = uuid.uuid4()
        transaction = AccountingTransaction(transaction_id)
        
        # Execute business logic on the aggregate
        transaction.create_transaction(
            command.transaction_date,
            command.description,
            command.entries
        )
        
        # Persist the new events
        await self.event_store.save_events(
            transaction.id,
            transaction.uncommitted_events,
            expected_version=0
        )
        
        # Publish events to the bus for other parts of the system
        for event in transaction.uncommitted_events:
            await self.event_bus.publish(event)
        
        transaction.mark_events_as_committed()
        
        return transaction.id
