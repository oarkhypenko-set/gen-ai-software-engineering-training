"""Shared helpers: storage access, error responses, filtering and balance math."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal
from typing import Iterable, Mapping

from flask import current_app, jsonify

from src.models import TRANSACTION_TYPES, Transaction, TransactionStore
from src.validators import is_valid_account

STORE_KEY = "transaction_store"
CENT = Decimal("0.01")


# --- Storage -----------------------------------------------------------------

def get_store() -> TransactionStore:
    """The TransactionStore registered on the current Flask app."""
    return current_app.extensions[STORE_KEY]


# --- Error responses ---------------------------------------------------------

def error_response(status: int, error: str, details: list[dict] | None = None):
    body = {"error": error}
    if details:
        body["details"] = details
    return jsonify(body), status


def validation_error(details: list[dict], error: str = "Validation failed"):
    return error_response(400, error, details)


# --- Dates -------------------------------------------------------------------

def parse_timestamp(value: str) -> datetime:
    """Parse an ISO 8601 datetime; naive values are treated as UTC."""
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _parse_bound(value: str, end_of_range: bool) -> datetime:
    """Parse a from/to query value.

    A date-only value (YYYY-MM-DD) covers the whole day: "from" starts at
    00:00 UTC, "to" ends just before 00:00 UTC of the next day.
    """
    if len(value) == 10:  # YYYY-MM-DD
        day = date.fromisoformat(value)
        if end_of_range:
            day += timedelta(days=1)
        start_of_day = datetime.combine(day, time.min, tzinfo=timezone.utc)
        return start_of_day - timedelta(microseconds=1) if end_of_range else start_of_day
    return parse_timestamp(value)


# --- Filtering ---------------------------------------------------------------

@dataclass
class TransactionFilters:
    account_id: str | None = None
    type: str | None = None
    start: datetime | None = None
    end: datetime | None = None

    def matches(self, tx: Transaction) -> bool:
        if self.account_id and self.account_id not in (tx.from_account, tx.to_account):
            return False
        if self.type and tx.type != self.type:
            return False
        if self.start or self.end:
            ts = parse_timestamp(tx.timestamp)
            if self.start and ts < self.start:
                return False
            if self.end and ts > self.end:
                return False
        return True


def parse_filters(args: Mapping[str, str]) -> tuple[TransactionFilters, list[dict]]:
    """Read accountId, type, from and to query parameters.

    Returns the filters and a list of {"field", "message"} errors.
    """
    filters = TransactionFilters()
    errors: list[dict] = []

    account_id = args.get("accountId")
    if account_id is not None:
        if is_valid_account(account_id):
            filters.account_id = account_id
        else:
            errors.append({"field": "accountId",
                           "message": "Account must follow the format ACC-XXXXX (X = letter or digit)"})

    tx_type = args.get("type")
    if tx_type is not None:
        if tx_type in TRANSACTION_TYPES:
            filters.type = tx_type
        else:
            errors.append({"field": "type",
                           "message": f"Type must be one of: {', '.join(TRANSACTION_TYPES)}"})

    for param, attr, end_of_range in (("from", "start", False), ("to", "end", True)):
        value = args.get(param)
        if value is None:
            continue
        try:
            setattr(filters, attr, _parse_bound(value, end_of_range))
        except ValueError:
            errors.append({"field": param,
                           "message": "Date must be ISO 8601 (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SSZ)"})

    if filters.start and filters.end and filters.start > filters.end:
        errors.append({"field": "from", "message": "'from' must not be later than 'to'"})

    return filters, errors


def filter_transactions(transactions: Iterable[Transaction],
                        filters: TransactionFilters) -> list[Transaction]:
    return [tx for tx in transactions if filters.matches(tx)]


# --- Money -------------------------------------------------------------------

def to_decimal(amount: float | int) -> Decimal:
    # str() avoids binary float artifacts: Decimal(0.1) != Decimal("0.1").
    return Decimal(str(amount))


def money(value: Decimal) -> float:
    """Round to cents and convert to a JSON-friendly float."""
    return float(value.quantize(CENT, rounding=ROUND_HALF_UP))


def account_transactions(transactions: Iterable[Transaction], account_id: str) -> list[Transaction]:
    return [tx for tx in transactions if account_id in (tx.from_account, tx.to_account)]


def calculate_balances(transactions: Iterable[Transaction], account_id: str) -> dict[str, Decimal]:
    """Balance per currency from completed transactions.

    Money flowing in (deposit, incoming transfer) is added; money flowing out
    (withdrawal, outgoing transfer) is subtracted. Currencies are not converted.
    """
    balances: dict[str, Decimal] = defaultdict(Decimal)
    for tx in transactions:
        if tx.status != "completed":
            continue
        amount = to_decimal(tx.amount)
        if tx.to_account == account_id:
            balances[tx.currency] += amount
        if tx.from_account == account_id:
            balances[tx.currency] -= amount
    return dict(sorted(balances.items()))


def has_sufficient_funds(transactions: Iterable[Transaction], account_id: str,
                         currency: str, amount: float | int) -> bool:
    """True if the account's completed balance in currency covers amount."""
    balance = calculate_balances(transactions, account_id).get(currency, Decimal(0))
    return balance >= to_decimal(amount)
