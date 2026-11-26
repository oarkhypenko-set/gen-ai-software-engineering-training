import threading

import pytest

from tests.conftest import deposit, transfer, withdrawal


# --- POST /transactions ------------------------------------------------------

def test_create_returns_201_with_generated_fields(post):
    response = post(**deposit(amount=500, currency="usd"))
    assert response.status_code == 201
    body = response.get_json()
    assert list(body) == ["id", "fromAccount", "toAccount", "amount", "currency",
                          "type", "timestamp", "status"]
    assert body["currency"] == "USD"
    assert body["amount"] == 500.0
    assert body["status"] == "completed"
    assert body["timestamp"].endswith("Z")
    assert response.headers["Location"] == f"/transactions/{body['id']}"


def test_client_cannot_set_id_status_or_timestamp(post):
    body = post(**deposit(), id="mine", status="failed",
                timestamp="2000-01-01T00:00:00Z").get_json()
    assert body["id"] != "mine"
    assert body["status"] == "completed"
    assert not body["timestamp"].startswith("2000")


def test_validation_error_format(post):
    response = post(**transfer(amount=-5, currency="XYZ"))
    assert response.status_code == 400
    assert response.get_json() == {
        "error": "Validation failed",
        "details": [
            {"field": "amount", "message": "Amount must be a positive number"},
            {"field": "currency", "message": "Invalid currency code"},
        ],
    }


@pytest.mark.parametrize("kwargs", [
    {"data": "not json", "content_type": "application/json"},
    {"data": "amount=5", "content_type": "application/x-www-form-urlencoded"},
    {"json": [1, 2]},
])
def test_create_rejects_non_object_bodies(client, kwargs):
    response = client.post("/transactions", **kwargs)
    assert response.status_code == 400
    assert response.get_json()["details"][0]["field"] == "body"


def test_invalid_transaction_is_not_stored(post, store):
    post(**deposit(amount=-1))
    assert len(store) == 0


# --- Insufficient funds ------------------------------------------------------

def status_of(response):
    assert response.status_code == 201
    return response.get_json()["status"]


def test_withdrawal_without_funds_is_failed(post):
    assert status_of(post(**withdrawal(amount=10))) == "failed"


def test_funds_check_allows_exact_balance(post):
    post(**deposit(amount=100))
    assert status_of(post(**withdrawal(amount=60))) == "completed"
    assert status_of(post(**transfer(amount=40.01))) == "failed"
    assert status_of(post(**transfer(amount=40))) == "completed"
    assert status_of(post(**withdrawal(amount=0.01))) == "failed"


def test_funds_are_checked_per_currency(post):
    post(**deposit(amount=100, currency="USD"))
    assert status_of(post(**withdrawal(amount=1, currency="EUR"))) == "failed"


def test_failed_transfer_does_not_credit_receiver(client, post):
    post(**transfer(amount=10))
    assert client.get("/accounts/ACC-67890/balance").get_json()["balances"] == {}


def test_concurrent_withdrawals_never_overdraw(app, post):
    post(**deposit(amount=10))
    statuses = []

    def worker():
        response = app.test_client().post("/transactions", json=withdrawal(amount=1))
        statuses.append(response.get_json()["status"])

    threads = [threading.Thread(target=worker) for _ in range(20)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert statuses.count("completed") == 10
    assert statuses.count("failed") == 10


# --- GET /transactions/<id> --------------------------------------------------

def test_get_by_id(client, post):
    created = post(**deposit()).get_json()
    response = client.get(f"/transactions/{created['id']}")
    assert response.status_code == 200
    assert response.get_json() == created


def test_get_unknown_id_returns_404(client):
    response = client.get("/transactions/does-not-exist")
    assert response.status_code == 404
    assert response.get_json() == {"error": "Transaction 'does-not-exist' not found"}


# --- GET /transactions with filters ------------------------------------------

@pytest.fixture
def history(add):
    add(id="t1", type="deposit", amount=100, to_account="ACC-12345",
        timestamp="2023-12-31T23:59:59Z")
    add(id="t2", type="deposit", amount=100, to_account="ACC-12345",
        timestamp="2024-01-01T00:00:00Z")
    add(id="t3", type="transfer", amount=50, from_account="ACC-12345", to_account="ACC-67890",
        timestamp="2024-01-15T10:00:00Z")
    add(id="t4", type="withdrawal", amount=10, from_account="ACC-67890",
        timestamp="2024-01-31T23:59:59Z")
    add(id="t5", type="deposit", amount=5, to_account="ACC-67890",
        timestamp="2024-02-01T00:00:00Z")


def ids(response):
    assert response.status_code == 200
    return [tx["id"] for tx in response.get_json()]


def test_list_all_in_insertion_order(client, history):
    assert ids(client.get("/transactions")) == ["t1", "t2", "t3", "t4", "t5"]


def test_list_empty(client):
    assert client.get("/transactions").get_json() == []


@pytest.mark.parametrize("query, expected", [
    ("accountId=ACC-12345", ["t1", "t2", "t3"]),
    ("accountId=ACC-67890", ["t3", "t4", "t5"]),
    ("accountId=ACC-99999", []),
    ("type=transfer", ["t3"]),
    ("type=deposit", ["t1", "t2", "t5"]),
    ("from=2024-01-01&to=2024-01-31", ["t2", "t3", "t4"]),
    ("from=2024-01-15", ["t3", "t4", "t5"]),
    ("to=2024-01-01", ["t1", "t2"]),
    ("from=2024-01-15T10:00:00Z&to=2024-01-15T10:00:00Z", ["t3"]),
    ("to=2024-01-15T11:00:00%2B02:00", ["t1", "t2"]),  # = 09:00Z, before t3
    ("accountId=ACC-67890&type=deposit", ["t5"]),
    ("accountId=ACC-12345&type=deposit&from=2024-01-01&to=2024-01-31", ["t2"]),
])
def test_filters(client, history, query, expected):
    assert ids(client.get(f"/transactions?{query}")) == expected


@pytest.mark.parametrize("query, field", [
    ("accountId=ACC-1", "accountId"),
    ("type=refund", "type"),
    ("from=yesterday", "from"),
    ("to=2024-13-01", "to"),
    ("from=2024-02-01&to=2024-01-01", "from"),
])
def test_invalid_filters_return_400(client, query, field):
    response = client.get(f"/transactions?{query}")
    assert response.status_code == 400
    body = response.get_json()
    assert body["error"] == "Invalid query parameters"
    assert [d["field"] for d in body["details"]] == [field]
