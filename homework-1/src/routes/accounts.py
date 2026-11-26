"""/accounts endpoints."""

from flask import Blueprint, jsonify

from src.utils.helpers import (
    account_transactions,
    calculate_balances,
    calculate_summary,
    error_response,
    get_store,
    money,
    validation_error,
)
from src.validators import is_valid_account

accounts_bp = Blueprint("accounts", __name__, url_prefix="/accounts")


def _load_account(account_id: str):
    """Return (transactions, None) or (None, error response).

    An account exists once any transaction references it.
    """
    if not is_valid_account(account_id):
        return None, validation_error([{
            "field": "accountId",
            "message": "Account must follow the format ACC-XXXXX (X = letter or digit)",
        }])
    transactions = account_transactions(get_store().all(), account_id)
    if not transactions:
        return None, error_response(404, f"Account '{account_id}' not found")
    return transactions, None


@accounts_bp.get("/<account_id>/balance")
def get_balance(account_id: str):
    transactions, error = _load_account(account_id)
    if error:
        return error

    balances = calculate_balances(transactions, account_id)
    return jsonify({
        "accountId": account_id,
        "balances": {currency: money(amount) for currency, amount in balances.items()},
    })


@accounts_bp.get("/<account_id>/summary")
def get_summary(account_id: str):
    transactions, error = _load_account(account_id)
    if error:
        return error

    return jsonify({"accountId": account_id, **calculate_summary(transactions, account_id)})
