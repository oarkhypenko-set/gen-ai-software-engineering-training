# 🏦 Homework 1: Banking Transactions API

> **Student Name**: Oleksandr Arkhypenko
> **Date Submitted**: 2026-11-26
> **AI Tools Used**: Claude Code (VS Code extension)

---

## 📋 Project Overview

A REST API for banking transactions built with **Python 3 + Flask**, using in-memory
storage. It supports deposits, withdrawals and transfers between `ACC-XXXXX` accounts in any
circulating ISO 4217 currency, with strict validation, filtering, per-currency balances, and
all four optional features from the assignment: **account summary, simple interest, CSV
export and rate limiting**. The code is covered by a 128-test `pytest` suite.

Run it with `demo/run.sh` (or `demo\run.bat` on Windows); see [HOWTORUN.md](HOWTORUN.md).

---

## ✅ Features Implemented

| Task | Feature | Status |
|------|---------|--------|
| 1 | Core endpoints: create, list, get by id, account balance | ✅ |
| 2 | Validation: amount, account format, ISO 4217 currency, meaningful error messages | ✅ |
| 3 | Filtering by account, type and date range (combinable) | ✅ |
| 4A | `GET /accounts/:accountId/summary` | ✅ |
| 4B | `GET /accounts/:accountId/interest?rate=&days=` | ✅ |
| 4C | `GET /transactions/export?format=csv` | ✅ |
| 4D | Rate limiting: 100 requests/minute per IP, `429` when exceeded | ✅ |
| Extra | No overdrafts: transactions that would make a balance negative are saved as `failed` | ✅ |
| Extra | JSON error responses for every error (404, 405, 413, 429, 500) | ✅ |
| Extra | Demo data loading, automated tests | ✅ |

### Endpoints

| Method | Endpoint | Success | Errors |
|--------|----------|---------|--------|
| `POST` | `/transactions` | `201` + transaction, `Location` header | `400` |
| `GET` | `/transactions?accountId=&type=&from=&to=` | `200` + array | `400` bad filter |
| `GET` | `/transactions/:id` | `200` | `404` |
| `GET` | `/transactions/export?format=csv` (same filters) | `200` `text/csv` | `400` |
| `GET` | `/accounts/:accountId/balance` | `200` | `400` bad id, `404` unknown account |
| `GET` | `/accounts/:accountId/summary` | `200` | `400`, `404` |
| `GET` | `/accounts/:accountId/interest?rate=0.05&days=30` | `200` | `400`, `404` |

Every endpoint can also return `429 Too Many Requests` (with a `Retry-After` header).

### Transaction model

```json
{
  "id": "1f126565-cba6-4357-86fe-7b4fcf5c523b",
  "fromAccount": "ACC-12345",
  "toAccount": "ACC-67890",
  "amount": 100.5,
  "currency": "USD",
  "type": "transfer",
  "timestamp": "2026-11-26T14:47:07.502Z",
  "status": "completed"
}
```

`id`, `timestamp` and `status` are always set by the server; if a client sends them they are
ignored.

### Validation rules (Task 2)

| Field | Rule |
|-------|------|
| `amount` | A JSON number, greater than 0, at most 2 decimal places. Strings, booleans, `NaN` and infinity are rejected. |
| `fromAccount` / `toAccount` | Format `ACC-` + exactly 5 letters or digits. Which fields are needed depends on the type (below). |
| `currency` | A circulating ISO 4217 code, case-insensitive (`usd` is stored as `USD`). Fund, metal and test codes such as `XAU` or `XXX` are rejected. |
| `type` | `deposit`, `withdrawal` or `transfer`. |

| Type | `fromAccount` | `toAccount` |
|------|---------------|-------------|
| `deposit` | must not be set | required |
| `withdrawal` | required | must not be set |
| `transfer` | required | required, different from `fromAccount` |

All fields are checked in one pass, so a response lists every problem at once:

```json
{
  "error": "Validation failed",
  "details": [
    {"field": "amount", "message": "Amount must be a positive number"},
    {"field": "currency", "message": "Invalid currency code"}
  ]
}
```

### Filtering (Task 3)

- `accountId` matches transactions where the account is either the sender or the receiver.
- `type` is one of the three transaction types.
- `from` / `to` accept a date (`2024-01-31`) or a full ISO 8601 timestamp
  (`2024-01-31T12:00:00Z`). A date covers the whole day, so
  `?from=2024-01-01&to=2024-01-31` includes everything on January 31.
- Filters can be combined. Invalid values, or `from` later than `to`, return `400`.

### Balance and the no-overdraft rule

The balance is calculated per currency from **completed** transactions only: deposits and
incoming transfers add, withdrawals and outgoing transfers subtract. Currencies are never
converted.

```json
GET /accounts/ACC-12345/balance
{"accountId": "ACC-12345", "balances": {"GBP": 450.5, "USD": 4299.75}}
```

A withdrawal or transfer larger than the sender's balance in that currency is still saved
(`201`), but with `"status": "failed"`, so it never affects any balance. The check and the
save happen under one lock, so parallel requests cannot spend the same money twice.

### Additional features (Task 4)

**A. Summary**: totals per currency (completed transactions only), counts and the latest
activity:

```json
GET /accounts/ACC-ABC12/summary
{
  "accountId": "ACC-ABC12",
  "totalDeposits": {"GBP": 3000.0},
  "totalWithdrawals": {"GBP": 500.0},
  "totalTransfersIn": {"GBP": 0.0},
  "totalTransfersOut": {"GBP": 450.5},
  "transactionCount": 4,
  "transactionCountByStatus": {"pending": 1, "completed": 3, "failed": 0},
  "mostRecentTransactionDate": "2024-02-10T15:00:00Z"
}
```

Transfers are reported separately from deposits and withdrawals, so the four totals add up
to the balance.

**B. Simple interest**: `balance × rate × days / 365` per currency, rounded to cents.
`rate` is a yearly fraction between 0 and 1 (`0.05` = 5%), `days` is a whole number from 1
to 3650.

```json
GET /accounts/ACC-12345/interest?rate=0.05&days=30
{
  "accountId": "ACC-12345", "rate": 0.05, "days": 30,
  "formula": "balance * rate * days / 365",
  "interest": {
    "GBP": {"balance": 450.5, "interest": 1.85, "projectedBalance": 452.35},
    "USD": {"balance": 4299.75, "interest": 17.67, "projectedBalance": 4317.42}
  }
}
```

**C. CSV export**: downloads `transactions-YYYYMMDD-HHMMSS.csv` with a header row,
two-decimal amounts and the same filters as `GET /transactions`:

```
id,fromAccount,toAccount,amount,currency,type,timestamp,status
tx-0005,,ACC-ABC12,3000.00,GBP,deposit,2024-01-10T11:20:00Z,completed
tx-0006,ACC-ABC12,ACC-12345,450.50,GBP,transfer,2024-01-15T16:05:00Z,completed
```

**D. Rate limiting**: at most 100 requests per minute per client IP, on every route. Every
response carries `X-RateLimit-Limit` and `X-RateLimit-Remaining`. Over the limit the API
answers `429` with a `Retry-After` header:

```json
{"error": "Too Many Requests",
 "message": "Rate limit of 100 requests per 60 seconds exceeded. Retry in 52 seconds."}
```

---

## 🏗️ Architecture Decisions

| Decision | Reason |
|----------|--------|
| **Flask with an app factory** (`create_app()`) and blueprints per resource | Each app gets its own store and settings, so tests are isolated and can turn features (rate limiting, demo data) on or off. |
| **In-memory store**: a dict keyed by id, guarded by a reentrant lock | Fast lookups by id, keeps insertion order for listing, and is safe for concurrent requests. The lock also covers "check balance, then save", so no overdraft slips through under load. |
| **`Decimal` for all money math**, converted to numbers only in responses | Float math gives results like `698.9499999`; `Decimal` gives exactly `698.95`. Interest is rounded to cents only at the end. |
| **Balances per currency, no conversion** | No exchange rates are available, and mixing currencies would give meaningless totals. |
| **Overdrafts are saved as `failed` rather than rejected with `400`** | The request itself is valid; the business rule decides the outcome. This keeps an audit trail of attempts and uses the `failed` status from the spec. |
| **Validation collects all errors** instead of stopping at the first | The client can fix everything in one round trip, matching the `details` array in the spec. |
| **Strict account rules per type** (e.g. a deposit must not have `fromAccount`) | Makes every transaction's effect on balances unambiguous. |
| **Every error is JSON**, through global error handlers | API clients never get an HTML error page; `405` keeps its `Allow` header. |
| **Sliding-window rate limiter** written by hand (no Flask-Limiter) | It is about 60 lines, has no extra dependency, and gives no burst at window boundaries as fixed windows do. Rejected requests do not extend the block. |
| **CSV cells starting with `=`, `+`, `-` or `@` are prefixed with `'`** | Prevents formula injection when the export is opened in Excel. |
| **Uses the direct client IP**, not `X-Forwarded-For` | The header can be faked by clients. Behind a reverse proxy, Werkzeug's `ProxyFix` should be added. |

### Project structure

```
homework-1/
├── README.md, HOWTORUN.md, TASKS.md, plan.txt
├── requirements.txt          # flask, pytest
├── pytest.ini
├── .gitignore
├── src/
│   ├── app.py                # create_app(), error handlers, demo data loading, entry point
│   ├── models/
│   │   └── transaction.py    # Transaction dataclass + thread-safe TransactionStore
│   ├── routes/
│   │   ├── transactions.py   # /transactions, /transactions/:id, /transactions/export
│   │   └── accounts.py       # /accounts/:id/balance, /summary, /interest
│   ├── validators/
│   │   └── transaction_validator.py
│   └── utils/
│       ├── currencies.py     # ISO 4217 codes
│       ├── helpers.py        # filters, balance/summary/interest math, CSV
│       └── rate_limiter.py
├── tests/                    # 128 pytest tests
├── demo/
│   ├── run.sh, run.bat       # set up .venv and start the server
│   ├── sample-requests.http  # for the VS Code REST Client extension
│   ├── sample-requests.sh    # the same requests with curl (bash)
│   ├── sample-requests.bat   # the same requests with curl.exe (Windows cmd)
│   └── sample-data.json      # 13 demo transactions, 4 accounts, 4 currencies
└── docs/screenshots/
```

---

## 🧪 Testing

```bash
.venv/Scripts/python -m pytest     # Windows (Git Bash)
.venv/bin/python -m pytest         # Linux/macOS
```

128 tests cover every validation rule, all endpoints and filters, exact balance, summary
and interest results, CSV output, the no-overdraft rule under 20 parallel requests, rate
limiting (with a fake clock) and the JSON error handlers. To check that the tests really
catch bugs, three bugs were introduced on purpose (allowing 3 decimals, removing the funds
check, an off-by-one in the rate limiter); each one made tests fail.

---

## 🤖 How AI Was Used

The project was built with **Claude Code** in VS Code, step by step:

1. **Planning**: Claude read `TASKS.md` and proposed an implementation plan, which was
   saved as [plan.txt](plan.txt) and adjusted (Flask; all four optional features).
2. **Implementation in small steps**: one prompt per plan step (setup, model, validation,
   routes, app factory, each optional feature, tests, docs), each reviewed and committed
   separately on the `homework-1-submission` branch.
3. **Testing each step**: after every step Claude ran the code against real requests
   before committing, which caught several bugs early:
   - a `type` sent as a JSON list crashed the validator (unhashable dict key);
   - `days=²` passed `str.isdigit()` but crashed `int()`, returning `500` instead of `400`;
   - Flask sorted response keys alphabetically instead of the spec's field order.
4. **Design decisions by the developer**: the AI flagged choices for review instead of
   deciding silently. One example is the no-overdraft rule: the first version allowed
   negative balances, and on review it was changed so those transactions are marked
   `failed`.

### Screenshots

Screenshots of the AI interactions, the running API and sample requests/responses are in
[docs/screenshots/](docs/screenshots/).

<div align="center">

*This project was completed as part of the AI-Assisted Development course.*

</div>
