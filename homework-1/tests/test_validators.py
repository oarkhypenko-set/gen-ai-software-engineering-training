import pytest

from src.utils.currencies import is_valid_currency
from src.validators import is_valid_account, validate_transaction
from tests.conftest import deposit, transfer, withdrawal


def fields(errors):
    return [e["field"] for e in errors]


@pytest.mark.parametrize("payload", [
    transfer(amount=100.5),
    deposit(amount=5),
    withdrawal(amount=0.01),
    deposit(account="ACC-ab12Z", currency="eur"),
    deposit(amount=1_000_000),
])
def test_valid_payloads(payload):
    assert validate_transaction(payload) == []


def test_spec_example_reports_all_errors():
    errors = validate_transaction(transfer(amount=-5, currency="XYZ"))
    assert errors == [
        {"field": "amount", "message": "Amount must be a positive number"},
        {"field": "currency", "message": "Invalid currency code"},
    ]


@pytest.mark.parametrize("payload", [None, [], "text", 42])
def test_body_must_be_object(payload):
    assert fields(validate_transaction(payload)) == ["body"]


def test_missing_required_fields():
    assert fields(validate_transaction({})) == ["amount", "currency", "type"]


@pytest.mark.parametrize("amount, message", [
    (0, "Amount must be a positive number"),
    (-1, "Amount must be a positive number"),
    ("10", "Amount must be a positive number"),
    (True, "Amount must be a positive number"),
    (float("nan"), "Amount must be a positive number"),
    (float("inf"), "Amount must be a positive number"),
    (1.005, "Amount must have at most 2 decimal places"),
    (0.1 + 0.2, "Amount must have at most 2 decimal places"),
    (1e-5, "Amount must have at most 2 decimal places"),
])
def test_invalid_amounts(amount, message):
    assert validate_transaction(deposit(amount=amount)) == [{"field": "amount", "message": message}]


@pytest.mark.parametrize("account", ["ACC-1234", "ACC-123456", "acc-12345", "ACC_12345",
                                     "ACC-1234!", "ACC-1234 ", 12345])
def test_invalid_account_format(account):
    assert fields(validate_transaction(deposit(account=account))) == ["toAccount"]


@pytest.mark.parametrize("currency", ["XYZ", "US", "usdd", "XAU", "XXX", 840, ""])
def test_invalid_currency(currency):
    assert fields(validate_transaction(deposit(currency=currency))) == ["currency"]


@pytest.mark.parametrize("tx_type", ["refund", "DEPOSIT", "", ["transfer"], {"a": 1}])
def test_invalid_type(tx_type):
    payload = {**transfer(), "type": tx_type}
    assert fields(validate_transaction(payload)) == ["type"]


def test_account_rules_by_type():
    assert validate_transaction({**deposit(), "fromAccount": "ACC-11111"}) == [
        {"field": "fromAccount", "message": "fromAccount must not be set for a deposit"}]
    assert validate_transaction({**withdrawal(), "toAccount": "ACC-11111"}) == [
        {"field": "toAccount", "message": "toAccount must not be set for a withdrawal"}]
    assert fields(validate_transaction({"amount": 1, "currency": "USD", "type": "transfer"})) == [
        "fromAccount", "toAccount"]


def test_transfer_to_same_account():
    assert validate_transaction(transfer(src="ACC-12345", dst="ACC-12345")) == [
        {"field": "toAccount", "message": "toAccount must be different from fromAccount"}]


def test_helpers():
    assert is_valid_account("ACC-A1b2C")
    assert not is_valid_account(None)
    assert is_valid_currency("gbp") and is_valid_currency("JPY")
    assert not is_valid_currency(None)
