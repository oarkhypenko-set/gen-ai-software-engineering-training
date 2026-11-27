"""/accounts endpoints."""

from flask import Blueprint, jsonify, request

from src.utils.helpers import (
    DAYS_PER_YEAR,
    account_transactions,
    calculate_balances,
    calculate_interest,
    calculate_summary,
    error_response,
    get_store,
    money,
    parse_interest_params,
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


@accounts_bp.get("/<account_id>/interest")
def get_interest(account_id: str):
    transactions, error = _load_account(account_id)
    if error:
        return error

    rate, days, errors = parse_interest_params(request.args)
    if errors:
        return validation_error(errors, error="Invalid query parameters")

    balances = calculate_balances(transactions, account_id)
    return jsonify({
        "accountId": account_id,
        "rate": float(rate),
        "days": days,
        "formula": f"balance * rate * days / {DAYS_PER_YEAR}",
        "interest": calculate_interest(balances, rate, days),
    })
