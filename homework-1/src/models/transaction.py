"""Transaction model and in-memory storage."""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

TRANSACTION_TYPES = ("deposit", "withdrawal", "transfer")
TRANSACTION_STATUSES = ("pending", "completed", "failed")


def utc_now_iso() -> str:
    """Current UTC time as ISO 8601 string, e.g. 2024-01-15T10:30:00.123Z."""
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


@dataclass
class Transaction:
    amount: float
    currency: str
    type: str
    from_account: str | None = None
    to_account: str | None = None
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = field(default_factory=utc_now_iso)
    status: str = "completed"

    def to_dict(self) -> dict:
        """Serialize using the camelCase field names from the API spec."""
        return {
            "id": self.id,
            "fromAccount": self.from_account,
            "toAccount": self.to_account,
            "amount": self.amount,
            "currency": self.currency,
            "type": self.type,
            "timestamp": self.timestamp,
            "status": self.status,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Transaction":
        """Build a transaction from camelCase data (request body or seed file).

        Assumes the data was already validated. id, timestamp and status are
        generated when missing.
        """
        kwargs = {
            "amount": data["amount"],
            "currency": data["currency"].upper(),
            "type": data["type"],
            "from_account": data.get("fromAccount"),
            "to_account": data.get("toAccount"),
        }
        for key in ("id", "timestamp", "status"):
            if data.get(key):
                kwargs[key] = data[key]
        return cls(**kwargs)


class TransactionStore:
    """Thread-safe in-memory transaction storage, preserving insertion order."""

    def __init__(self) -> None:
        self._items: dict[str, Transaction] = {}
        self._lock = threading.Lock()

    def add(self, transaction: Transaction) -> Transaction:
        with self._lock:
            self._items[transaction.id] = transaction
        return transaction

    def get(self, transaction_id: str) -> Transaction | None:
        with self._lock:
            return self._items.get(transaction_id)

    def all(self) -> list[Transaction]:
        with self._lock:
            return list(self._items.values())

    def clear(self) -> None:
        with self._lock:
            self._items.clear()

    def __len__(self) -> int:
        with self._lock:
            return len(self._items)
