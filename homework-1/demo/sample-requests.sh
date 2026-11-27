#!/usr/bin/env bash
# Run sample requests against a running API and print each status code and body.
#
#   ./demo/sample-requests.sh                 all requests, then the rate-limit demo
#   ./demo/sample-requests.sh --no-rate-limit skip the rate-limit demo
#   BASE_URL=http://localhost:5000 ./demo/sample-requests.sh
#
# Start the server first (demo/run.sh). Best run against fresh demo data.
set -uo pipefail

BASE_URL="${BASE_URL:-http://localhost:3000}"

request() {
    local title="$1"; shift
    echo
    echo "=== $title"
    echo "\$ curl $*"
    curl -s -w '\n--> HTTP %{http_code}\n' "$@"
}

post() {
    request "$1" -X POST "$BASE_URL/transactions" -H "Content-Type: application/json" -d "$2"
}

if ! curl -s -o /dev/null "$BASE_URL/transactions"; then
    echo "API is not reachable at $BASE_URL. Start it with demo/run.sh first." >&2
    exit 1
fi

echo "##### Task 1: core endpoints"
post "Create a deposit (201)" \
    '{"toAccount": "ACC-12345", "amount": 500, "currency": "USD", "type": "deposit"}'
post "Create a transfer (201)" \
    '{"fromAccount": "ACC-12345", "toAccount": "ACC-67890", "amount": 100.50, "currency": "USD", "type": "transfer"}'
post "Withdrawal larger than the balance (201, status failed)" \
    '{"fromAccount": "ACC-12345", "amount": 1000000, "currency": "USD", "type": "withdrawal"}'
request "List all transactions (200)" "$BASE_URL/transactions"
request "Get transaction by id (200)" "$BASE_URL/transactions/tx-0003"
request "Unknown transaction id (404)" "$BASE_URL/transactions/does-not-exist"
request "Account balance (200)" "$BASE_URL/accounts/ACC-12345/balance"

echo; echo "##### Task 2: validation"
post "Negative amount and invalid currency (400)" \
    '{"fromAccount": "ACC-12345", "toAccount": "ACC-67890", "amount": -5, "currency": "XYZ", "type": "transfer"}'
post "3 decimals, bad accounts, unknown type (400)" \
    '{"fromAccount": "12345", "toAccount": "ACC-678", "amount": 10.555, "currency": "USD", "type": "refund"}'

echo; echo "##### Task 3: filtering"
request "By account (200)" "$BASE_URL/transactions?accountId=ACC-67890"
request "By type (200)" "$BASE_URL/transactions?type=transfer"
request "By date range (200)" "$BASE_URL/transactions?from=2024-01-01&to=2024-01-10"
request "Combined (200)" "$BASE_URL/transactions?accountId=ACC-12345&type=deposit&from=2024-01-01&to=2024-12-31"
request "Invalid filters (400)" "$BASE_URL/transactions?accountId=bad&from=yesterday"

echo; echo "##### Task 4: additional features"
request "A. Account summary (200)" "$BASE_URL/accounts/ACC-12345/summary"
request "B. Interest 5% for 30 days (200)" "$BASE_URL/accounts/ACC-12345/interest?rate=0.05&days=30"
request "B. Invalid interest parameters (400)" "$BASE_URL/accounts/ACC-12345/interest?rate=5&days=0"
request "C. CSV export (200)" "$BASE_URL/transactions/export?format=csv&accountId=ACC-ABC12"
request "C. Unsupported format (400)" "$BASE_URL/transactions/export?format=xml"

if [ "${1:-}" != "--no-rate-limit" ]; then
    echo; echo "##### D. Rate limiting: sending requests until the API answers 429"
    for i in $(seq 1 110); do
        code=$(curl -s -o /dev/null -w '%{http_code}' "$BASE_URL/transactions?type=deposit")
        if [ "$code" = "429" ]; then
            echo "Request #$i in this burst was rejected:"
            curl -s -i "$BASE_URL/transactions" | grep -iE '^(HTTP|retry-after|x-ratelimit)|error'
            break
        fi
    done
fi
