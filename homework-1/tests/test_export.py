import csv
import io

import pytest

HEADER = "id,fromAccount,toAccount,amount,currency,type,timestamp,status"


@pytest.fixture
def data(add):
    add(id="tx-1", type="deposit", amount=1000, to_account="ACC-12345",
        timestamp="2024-01-05T09:00:00Z")
    add(id="tx-2", type="transfer", amount=250.5, currency="EUR", from_account="ACC-12345",
        to_account="ACC-67890", timestamp="2024-02-10T12:00:00Z")


def test_export_csv(client, data):
    response = client.get("/transactions/export?format=csv")
    assert response.status_code == 200
    assert response.content_type == "text/csv; charset=utf-8"
    assert response.headers["Content-Disposition"].startswith('attachment; filename="transactions-')
    assert response.get_data(as_text=True) == (
        f"{HEADER}\r\n"
        "tx-1,,ACC-12345,1000.00,USD,deposit,2024-01-05T09:00:00Z,completed\r\n"
        "tx-2,ACC-12345,ACC-67890,250.50,EUR,transfer,2024-02-10T12:00:00Z,completed\r\n"
    )


def test_export_is_parseable(client, data):
    rows = list(csv.DictReader(io.StringIO(client.get("/transactions/export").get_data(as_text=True))))
    assert [row["id"] for row in rows] == ["tx-1", "tx-2"]
    assert rows[1]["amount"] == "250.50"


@pytest.mark.parametrize("query", ["", "?format=csv", "?format=CSV"])
def test_format_defaults_and_case(client, query):
    assert client.get(f"/transactions/export{query}").status_code == 200


def test_export_applies_filters(client, data):
    lines = client.get("/transactions/export?type=transfer&from=2024-02-01").get_data(as_text=True).splitlines()
    assert len(lines) == 2
    assert lines[0] == HEADER
    assert lines[1].startswith("tx-2,")


def test_export_empty(client):
    assert client.get("/transactions/export").get_data(as_text=True) == f"{HEADER}\r\n"


def test_export_invalid_params(client):
    response = client.get("/transactions/export?format=xml&type=bad")
    assert response.status_code == 400
    assert [d["field"] for d in response.get_json()["details"]] == ["format", "type"]


def test_export_escapes_formula_cells(client, add):
    add(id='=HYPERLINK("x")', type="deposit", amount=1, to_account="ACC-12345")
    row = list(csv.reader(io.StringIO(client.get("/transactions/export").get_data(as_text=True))))[1]
    assert row[0] == "'=HYPERLINK(\"x\")"


def test_export_route_does_not_shadow_get_by_id(client, data):
    assert client.get("/transactions/tx-1").status_code == 200
