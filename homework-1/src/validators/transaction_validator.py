"""Validation rules for incoming transaction requests."""

from __future__ import annotations

import math
import re
from decimal import Decimal

from src.models import TRANSACTION_TYPES
from src.utils.currencies import is_valid_currency

ACCOUNT_PATTERN = re.compile(r"ACC-[A-Za-z0-9]{5}")

# Which account fields each transaction type needs ("required") or must not have ("forbidden").
ACCOUNT_RULES = {
    "deposit": {"required": ("toAccount",), "forbidden": ("fromAccount",)},
    "withdrawal": {"required": ("fromAccount",), "forbidden": ("toAccount",)},
    "transfer": {"required": ("fromAccount", "toAccount"), "forbidden": ()},
}


def is_valid_account(account_id: object) -> bool:
    """True if account_id matches the ACC-XXXXX format (X = letter or digit)."""
    return isinstance(account_id, str) and ACCOUNT_PATTERN.fullmatch(account_id) is not None


def _error(field: str, message: str) -> dict:
    return {"field": field, "message": message}


def _validate_amount(payload: dict) -> list[dict]:
    if "amount" not in payload or payload["amount"] is None:
        return [_error("amount", "Amount is required")]

    amount = payload["amount"]
    # bool is a subclass of int, so it must be rejected explicitly.
    if isinstance(amount, bool) or not isinstance(amount, (int, float)):
        return [_error("amount", "Amount must be a positive number")]
    if isinstance(amount, float) and not math.isfinite(amount):
        return [_error("amount", "Amount must be a positive number")]
    if amount <= 0:
        return [_error("amount", "Amount must be a positive number")]

    # str() gives the shortest repr of a float, so 100.5 -> "100.5" and
    # 0.1 + 0.2 -> "0.30000000000000004" (correctly rejected).
    exponent = Decimal(str(amount)).as_tuple().exponent
    if isinstance(exponent, int) and exponent < -2:
        return [_error("amount", "Amount must have at most 2 decimal places")]
    return []


def _validate_type(payload: dict) -> list[dict]:
    tx_type = payload.get("type")
    if tx_type is None:
        return [_error("type", "Type is required")]
    if tx_type not in TRANSACTION_TYPES:
        return [_error("type", f"Type must be one of: {', '.join(TRANSACTION_TYPES)}")]
    return []


def _validate_currency(payload: dict) -> list[dict]:
    currency = payload.get("currency")
    if currency is None:
        return [_error("currency", "Currency is required")]
    if not is_valid_currency(currency):
        return [_error("currency", "Invalid currency code")]
    return []


def _validate_accounts(payload: dict) -> list[dict]:
    errors = []
    tx_type = payload.get("type")
    # Type may be any JSON value (e.g. a list), which is not hashable.
    rules = ACCOUNT_RULES.get(tx_type) if isinstance(tx_type, str) else None

    for field in ("fromAccount", "toAccount"):
        value = payload.get(field)
        if value is None:
            if rules and field in rules["required"]:
                errors.append(_error(field, f"{field} is required for a {payload['type']}"))
        elif rules and field in rules["forbidden"]:
            errors.append(_error(field, f"{field} must not be set for a {payload['type']}"))
        elif not is_valid_account(value):
            errors.append(_error(field, "Account must follow the format ACC-XXXXX (X = letter or digit)"))

    if (
        not errors
        and payload.get("type") == "transfer"
        and payload.get("fromAccount") == payload.get("toAccount")
    ):
        errors.append(_error("toAccount", "toAccount must be different from fromAccount"))
    return errors


def validate_transaction(payload: object) -> list[dict]:
    """Validate a create-transaction request body.

    Returns a list of {"field", "message"} errors; an empty list means valid.
    All checks run so the client sees every problem at once.
    """
    if not isinstance(payload, dict):
        return [_error("body", "Request body must be a JSON object")]

    return (
        _validate_amount(payload)
        + _validate_currency(payload)
        + _validate_type(payload)
        + _validate_accounts(payload)
    )
