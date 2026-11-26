import pytest


@pytest.fixture
def account(add):
    """ACC-12345: +1000 USD, +200 EUR, -250.75 USD out, +50 USD in, -100.1 and -0.2 USD.

    Plus one failed withdrawal that must be ignored in all totals.
    """
    add(type="deposit", amount=1000, to_account="ACC-12345", timestamp="2024-01-05T09:00:00Z")
    add(type="deposit", amount=200, currency="EUR", to_account="ACC-12345",
        timestamp="2024-01-06T09:00:00Z")
    add(type="transfer", amount=250.75, from_account="ACC-12345", to_account="ACC-67890",
        timestamp="2024-01-10T12:00:00Z")
    add(type="transfer", amount=50, from_account="ACC-67890", to_account="ACC-12345",
        timestamp="2024-01-12T12:00:00Z")
    add(type="withdrawal", amount=100.1, from_account="ACC-12345",
        timestamp="2024-01-15T08:00:00+02:00")  # 06:00Z
    add(type="withdrawal", amount=0.2, from_account="ACC-12345",
        timestamp="2024-01-15T07:00:00Z")       # the most recent
    add(type="withdrawal", amount=9999, from_account="ACC-12345",
        timestamp="2024-01-14T10:00:00Z", status="failed")


ENDPOINTS = ["balance", "summary", "interest?rate=0.05&days=30"]


@pytest.mark.parametrize("endpoint", ENDPOINTS)
def test_invalid_account_returns_400(client, endpoint):
    response = client.get(f"/accounts/bad-id/{endpoint}")
    assert response.status_code == 400
    assert response.get_json()["details"][0]["field"] == "accountId"


@pytest.mark.parametrize("endpoint", ENDPOINTS)
def test_unknown_account_returns_404(client, endpoint):
    response = client.get(f"/accounts/ACC-00000/{endpoint}")
    assert response.status_code == 404
    assert response.get_json() == {"error": "Account 'ACC-00000' not found"}


# --- Balance -----------------------------------------------------------------

def test_balance_per_currency_ignores_failed(client, account):
    response = client.get("/accounts/ACC-12345/balance")
    assert response.status_code == 200
    # 1000 + 50 - 250.75 - 100.1 - 0.2 = 698.95 exactly (no float drift)
    assert response.get_json() == {"accountId": "ACC-12345",
                                   "balances": {"EUR": 200.0, "USD": 698.95}}


def test_balance_of_transfer_receiver(client, account):
    assert client.get("/accounts/ACC-67890/balance").get_json()["balances"] == {"USD": 200.75}


def test_balance_after_api_calls(client, post):
    post(toAccount="ACC-12345", amount=500, currency="USD", type="deposit")
    post(fromAccount="ACC-12345", toAccount="ACC-67890", amount=100.5, currency="USD", type="transfer")
    assert client.get("/accounts/ACC-12345/balance").get_json()["balances"] == {"USD": 399.5}


# --- Summary (feature A) -----------------------------------------------------

def test_summary(client, account):
    response = client.get("/accounts/ACC-12345/summary")
    assert response.status_code == 200
    assert response.get_json() == {
        "accountId": "ACC-12345",
        "totalDeposits": {"EUR": 200.0, "USD": 1000.0},
        "totalWithdrawals": {"EUR": 0.0, "USD": 100.3},
        "totalTransfersIn": {"EUR": 0.0, "USD": 50.0},
        "totalTransfersOut": {"EUR": 0.0, "USD": 250.75},
        "transactionCount": 7,
        "transactionCountByStatus": {"pending": 0, "completed": 6, "failed": 1},
        "mostRecentTransactionDate": "2024-01-15T07:00:00Z",
    }


def test_summary_of_transfer_receiver(client, account):
    body = client.get("/accounts/ACC-67890/summary").get_json()
    assert body["totalTransfersIn"] == {"USD": 250.75}
    assert body["totalTransfersOut"] == {"USD": 50.0}
    assert body["transactionCount"] == 2


# --- Interest (feature B) ----------------------------------------------------

def test_interest(client, add):
    add(type="deposit", amount=1000, to_account="ACC-12345")
    response = client.get("/accounts/ACC-12345/interest?rate=0.05&days=30")
    assert response.status_code == 200
    assert response.get_json() == {
        "accountId": "ACC-12345",
        "rate": 0.05,
        "days": 30,
        "formula": "balance * rate * days / 365",
        # 1000 * 0.05 * 30 / 365 = 4.1095... -> 4.11
        "interest": {"USD": {"balance": 1000.0, "interest": 4.11, "projectedBalance": 1004.11}},
    }


def test_interest_full_year_and_zero_rate(client, add):
    add(type="deposit", amount=1000, to_account="ACC-12345")
    url = "/accounts/ACC-12345/interest"
    assert client.get(f"{url}?rate=0.1&days=365").get_json()["interest"]["USD"]["interest"] == 100.0
    assert client.get(f"{url}?rate=0&days=1").get_json()["interest"]["USD"]["interest"] == 0.0


@pytest.mark.parametrize("query, fields", [
    ("", ["rate", "days"]),
    ("?days=30", ["rate"]),
    ("?rate=0.05", ["days"]),
    ("?rate=5&days=30", ["rate"]),
    ("?rate=-0.01&days=30", ["rate"]),
    ("?rate=abc&days=30", ["rate"]),
    ("?rate=nan&days=30", ["rate"]),
    ("?rate=inf&days=30", ["rate"]),
    ("?rate=0.05&days=0", ["days"]),
    ("?rate=0.05&days=1.5", ["days"]),
    ("?rate=0.05&days=-3", ["days"]),
    ("?rate=0.05&days=3651", ["days"]),
    ("?rate=0.05&days=%C2%B2", ["days"]),  # "²" passes isdigit() but not int()
])
def test_interest_invalid_params(client, add, query, fields):
    add(type="deposit", amount=1000, to_account="ACC-12345")
    response = client.get(f"/accounts/ACC-12345/interest{query}")
    assert response.status_code == 400
    assert [d["field"] for d in response.get_json()["details"]] == fields
