import json

import pytest

from src.app import create_app


# --- JSON error handlers -----------------------------------------------------

def test_unknown_route_returns_json_404(client):
    response = client.get("/nope")
    assert response.status_code == 404
    assert response.is_json
    assert response.get_json()["error"] == "Not Found"


def test_wrong_method_returns_json_405_with_allow_header(client):
    response = client.delete("/transactions")
    assert response.status_code == 405
    assert response.get_json()["error"] == "Method Not Allowed"
    assert "POST" in response.headers["Allow"]


def test_body_too_large_returns_413(client):
    response = client.post("/transactions", data="x" * (1024 * 1024 + 1),
                           content_type="application/json")
    assert response.status_code == 413
    assert response.is_json


def test_unexpected_error_returns_json_500(app):
    @app.get("/boom")
    def boom():
        raise RuntimeError("secret details")

    response = app.test_client().get("/boom")
    assert response.status_code == 500
    assert response.get_json() == {"error": "Internal Server Error",
                                   "message": "An unexpected error occurred"}


# --- Seed data ---------------------------------------------------------------

def make_app(seed_file):
    return create_app({"TESTING": True, "RATE_LIMIT_ENABLED": False,
                       "SEED_DATA": True, "SEED_DATA_FILE": str(seed_file)})


def test_seed_loads_valid_records_and_skips_invalid(tmp_path):
    seed = tmp_path / "seed.json"
    seed.write_text(json.dumps([
        {"id": "tx-1", "toAccount": "ACC-12345", "amount": 1000, "currency": "USD",
         "type": "deposit", "timestamp": "2024-01-05T09:00:00Z"},
        {"id": "tx-2", "fromAccount": "ACC-12345", "toAccount": "ACC-67890", "amount": 250.75,
         "currency": "usd", "type": "transfer", "status": "pending"},
        {"id": "tx-2", "toAccount": "ACC-12345", "amount": 5, "currency": "USD", "type": "deposit"},
        {"toAccount": "ACC-12345", "amount": 5, "currency": "USD", "type": "deposit", "status": "odd"},
        {"toAccount": "ACC-12345", "amount": 5, "currency": "USD", "type": "deposit",
         "timestamp": "not-a-date"},
        {"toAccount": "BAD", "amount": -1, "currency": "USD", "type": "deposit"},
        "not an object",
    ]))
    client = make_app(seed).test_client()

    transactions = client.get("/transactions").get_json()
    assert [tx["id"] for tx in transactions] == ["tx-1", "tx-2"]
    assert transactions[1]["status"] == "pending"
    assert transactions[1]["currency"] == "USD"
    # The pending transfer does not count towards the balance.
    assert client.get("/accounts/ACC-12345/balance").get_json()["balances"] == {"USD": 1000.0}


@pytest.mark.parametrize("content", [None, "not json", '{"an": "object"}'])
def test_bad_seed_file_starts_empty(tmp_path, content):
    seed = tmp_path / "seed.json"
    if content is not None:
        seed.write_text(content)
    assert len(make_app(seed).extensions["transaction_store"]) == 0


def test_no_seed_by_default():
    assert len(create_app({"TESTING": True}).extensions["transaction_store"]) == 0


def test_apps_do_not_share_state():
    first, second = create_app({"TESTING": True}), create_app({"TESTING": True})
    first.test_client().post("/transactions", json={"toAccount": "ACC-12345", "amount": 1,
                                                    "currency": "USD", "type": "deposit"})
    assert second.test_client().get("/transactions").get_json() == []
