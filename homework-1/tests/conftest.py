import pytest

from src.app import create_app
from src.models import Transaction


@pytest.fixture
def app():
    # Rate limiting is off by default in tests; test_rate_limiter enables it.
    return create_app({"TESTING": True, "RATE_LIMIT_ENABLED": False})


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def store(app):
    return app.extensions["transaction_store"]


@pytest.fixture
def add(store):
    """Insert a transaction directly (bypasses the API and the funds check)."""
    def _add(**kwargs):
        kwargs.setdefault("currency", "USD")
        kwargs.setdefault("timestamp", "2024-01-15T12:00:00Z")
        return store.add(Transaction(**kwargs))
    return _add


@pytest.fixture
def post(client):
    """POST /transactions with a JSON body and return the response."""
    def _post(**body):
        return client.post("/transactions", json=body)
    return _post


def deposit(account="ACC-12345", amount=100, currency="USD"):
    return {"toAccount": account, "amount": amount, "currency": currency, "type": "deposit"}


def withdrawal(account="ACC-12345", amount=10, currency="USD"):
    return {"fromAccount": account, "amount": amount, "currency": currency, "type": "withdrawal"}


def transfer(src="ACC-12345", dst="ACC-67890", amount=10, currency="USD"):
    return {"fromAccount": src, "toAccount": dst, "amount": amount,
            "currency": currency, "type": "transfer"}
