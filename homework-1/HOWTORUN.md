# ▶️ How to Run the Application

## Prerequisites

- **Python 3.11 or newer** (`python --version`)
- `curl` or VS Code with the **REST Client** extension, to send requests (optional)

All commands below are run from the `homework-1` folder.

---

## Option 1: Run script (recommended)

The script creates a virtual environment in `.venv` (first run only), installs the
dependencies and starts the server with the demo data from `demo/sample-data.json`.

**Windows (Command Prompt or PowerShell):**

```bat
demo\run.bat
```

**Linux / macOS / Git Bash:**

```bash
chmod +x demo/run.sh   # first time only
./demo/run.sh
```

The API is ready when you see:

```
Starting API on http://localhost:3000 (seed data: 1). Press Ctrl+C to stop.
INFO:__main__:Loaded 13 seed transactions from ...demo/sample-data.json
 * Running on http://127.0.0.1:3000
```

Press **Ctrl+C** to stop it. Data is kept in memory only, so it resets on every restart.

To start **without demo data**:

```bash
SEED_DATA=0 ./demo/run.sh              # Linux / macOS / Git Bash
```

```bat
set SEED_DATA=0
demo\run.bat
```

---

## Option 2: Manual setup

1. Create and activate a virtual environment:

   ```bash
   python -m venv .venv
   .venv\Scripts\activate         # Windows
   source .venv/bin/activate      # Linux / macOS
   ```

2. Install the dependencies:

   ```bash
   pip install -r requirements.txt
   ```

3. Start the server:

   ```bash
   python -m src.app
   ```

   To load the demo data, set `SEED_DATA=1` first (`set SEED_DATA=1` on Windows,
   `export SEED_DATA=1` on Linux/macOS).

   Alternatively: `flask --app src.app run -p 3000`.

---

## Configuration

| Environment variable | Default | Meaning |
|----------------------|---------|---------|
| `PORT` | `3000` | Port to listen on |
| `HOST` | `127.0.0.1` | Address to bind to (`0.0.0.0` to allow other machines) |
| `SEED_DATA` | `1` in the run scripts, `0` otherwise | `1` loads the demo data at startup |
| `SEED_DATA_FILE` | `demo/sample-data.json` | Path to another seed file (a JSON array of transactions) |
| `RATE_LIMIT` | `100` | Requests allowed per minute per IP |
| `FLASK_DEBUG` | `0` | `1` enables debug mode with auto-reload |

---

## Try the API

With the server running:

**Quick check with curl:**

```bash
curl http://localhost:3000/transactions
curl http://localhost:3000/accounts/ACC-12345/balance

curl -X POST http://localhost:3000/transactions \
  -H "Content-Type: application/json" \
  -d '{"fromAccount": "ACC-12345", "toAccount": "ACC-67890", "amount": 100.50, "currency": "USD", "type": "transfer"}'
```

> In Windows PowerShell, use `curl.exe` instead of `curl`, and put the JSON body in a file
> (`-d "@body.json"`) to avoid quoting problems.

**All sample requests at once (curl):**

```bash
./demo/sample-requests.sh                   # ends with a rate-limit demo (sends ~100 requests)
./demo/sample-requests.sh --no-rate-limit   # skip the rate-limit demo
```

Each request prints its status code and response body. Best run right after a fresh start
with demo data.

**VS Code REST Client:** open `demo/sample-requests.http` and click **Send Request** above
any request. It covers every endpoint, validation errors, filters and the optional
features.

**Demo accounts** (with demo data loaded):

| Account | Balances |
|---------|----------|
| `ACC-12345` | 4299.75 USD, 450.50 GBP |
| `ACC-67890` | 1100.01 EUR, 450.25 USD |
| `ACC-ABC12` | 2049.50 GBP |
| `ACC-XYZ99` | 300.00 USD, 150000.00 JPY |

---

## Run the tests

```bash
./demo/run.sh test           # Linux / macOS / Git Bash
demo\run.bat test            # Windows
```

or directly: `python -m pytest` with the virtual environment active. Expected result:
`128 passed`.

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `Address already in use` / port 3000 busy | Stop the other process, or start on another port: `PORT=5000 ./demo/run.sh` (`set PORT=5000` on Windows). |
| `python` not found | Install Python 3.11+ and make sure it is on `PATH` (on Windows, tick "Add python.exe to PATH" in the installer). |
| `ModuleNotFoundError: No module named 'src'` | Run commands from the `homework-1` folder, and start with `python -m src.app`, not `python src/app.py`. |
| `./demo/run.sh: Permission denied` | Run `chmod +x demo/run.sh demo/sample-requests.sh`. |
| `429 Too Many Requests` | Over 100 requests in a minute; wait for the number of seconds in the `Retry-After` header. |
| `/accounts/.../balance` returns `404` | No transaction mentions that account yet; create one, or start with demo data. |
