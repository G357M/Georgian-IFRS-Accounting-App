import uuid
from decimal import Decimal
from dataclasses import dataclass, field
from typing import List, Optional
from datetime import datetime

from new_system.events.base import Aggregate, DomainEvent

@dataclass
class JournalEntryData:
    account_id: uuid.UUID
    debit: Decimal
    credit: Decimal
    description: str

class AccountingTransaction(Aggregate):
    """Aggregate for an accounting transaction."""
    
    def __init__(self, aggregate_id: uuid.UUID):
        super().__init__(aggregate_id)
        self.transaction_date: Optional[datetime] = None
        self.description: str = ""
        self.entries: List[JournalEntryData] = []
        self.status: str = "initial"
        self.total_debit: Decimal = Decimal('0.00')
        self.total_credit: Decimal = Decimal('0.00')
    
    def create_transaction(self, transaction_date: datetime, description: str, entries: List[JournalEntryData]):
        if self.status != "initial":
            raise ValueError("Transaction has already been created.")
        
        total_debit = sum(entry.debit for entry in entries)
        total_credit = sum(entry.credit for entry in entries)
        
        if total_debit != total_credit:
            raise ValueError(f"Unbalanced transaction: debit={total_debit}, credit={total_credit}")
        
        if total_debit <= 0:
            raise ValueError("Transaction amount must be positive.")

        self.raise_event("TransactionCreated", {
            "transaction_date": transaction_date.isoformat(),
            "description": description,
            "entries": [
                {
                    "account_id": str(entry.account_id),
                    "debit": str(entry.debit),
                    "credit": str(entry.credit),
                    "description": entry.description
                }
                for entry in entries
            ],
            "total_amount": str(total_debit)
        })

    def approve_transaction(self, approved_by: uuid.UUID):
        if self.status != "draft":
            raise ValueError(f"Cannot approve transaction with status: {self.status}")
        
        self.raise_event("TransactionApproved", {
            "approved_by": str(approved_by),
            "approved_at": datetime.utcnow().isoformat()
        })

    def post_transaction(self, posted_by: uuid.UUID):
        if self.status != "approved":
            raise ValueError(f"Cannot post transaction with status: {self.status}")
        
        self.raise_event("TransactionPosted", {
            "posted_by": str(posted_by),
            "posted_at": datetime.utcnow().isoformat()
        })

    # Event handlers that mutate the aggregate's state
    def _on_transactioncreated(self, event: DomainEvent):
        self.transaction_date = datetime.fromisoformat(event.event_data["transaction_date"])
        self.description = event.event_data["description"]
        self.entries = [
            JournalEntryData(
                account_id=uuid.UUID(entry["account_id"]),
                debit=Decimal(entry["debit"]),
                credit=Decimal(entry["credit"]),
                description=entry["description"]
            )
            for entry in event.event_data["entries"]
        ]
        self.total_debit = self.total_credit = Decimal(event.event_data["total_amount"])
        self.status = "draft"
            
    def _on_transactionapproved(self, event: DomainEvent):
        self.status = "approved"
            
    def _on_transactionposted(self, event: DomainEvent):
        self.status = "posted"
