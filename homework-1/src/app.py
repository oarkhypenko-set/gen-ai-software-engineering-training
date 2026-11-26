"""Application factory and entry point for the Banking Transactions API.

Run from the homework-1 directory:
    python -m src.app                 (http://127.0.0.1:3000)
    flask --app src.app run -p 3000
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

from flask import Flask, jsonify
from werkzeug.exceptions import HTTPException

from src.models import TRANSACTION_STATUSES, Transaction, TransactionStore
from src.routes import accounts_bp, transactions_bp
from src.utils.helpers import STORE_KEY, parse_timestamp
from src.validators import validate_transaction

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SEED_FILE = PROJECT_ROOT / "demo" / "sample-data.json"


def create_app(config: dict | None = None) -> Flask:
    app = Flask(__name__)
    app.config.update(
        MAX_CONTENT_LENGTH=1024 * 1024,  # 1 MB request bodies are plenty
        SEED_DATA=os.environ.get("SEED_DATA") == "1",
        SEED_DATA_FILE=os.environ.get("SEED_DATA_FILE", str(DEFAULT_SEED_FILE)),
    )
    if config:
        app.config.update(config)

    # Keep fields in the order defined by the API spec instead of sorting them.
    app.json.sort_keys = False

    store = TransactionStore()
    app.extensions[STORE_KEY] = store

    app.register_blueprint(transactions_bp)
    app.register_blueprint(accounts_bp)
    _register_error_handlers(app)

    if app.config["SEED_DATA"]:
        loaded = load_seed_data(store, Path(app.config["SEED_DATA_FILE"]))
        logger.info("Loaded %d seed transactions from %s", loaded, app.config["SEED_DATA_FILE"])

    return app


def _register_error_handlers(app: Flask) -> None:
    @app.errorhandler(HTTPException)
    def handle_http_error(error: HTTPException):
        # get_response() keeps useful headers such as Allow (405).
        response = error.get_response()
        response.data = json.dumps({"error": error.name, "message": error.description})
        response.content_type = "application/json"
        return response

    @app.errorhandler(Exception)
    def handle_unexpected_error(error: Exception):
        logger.exception("Unhandled error")
        return jsonify({"error": "Internal Server Error",
                        "message": "An unexpected error occurred"}), 500


def load_seed_data(store: TransactionStore, path: Path) -> int:
    """Load transactions from a JSON array file. Invalid records are skipped.

    Seed records may set id, timestamp and status; they are trusted as given
    (no balance check), so the file controls the demo state exactly.
    """
    try:
        records = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Could not read seed file %s: %s", path, exc)
        return 0
    if not isinstance(records, list):
        logger.warning("Seed file %s must contain a JSON array", path)
        return 0

    loaded = 0
    for index, record in enumerate(records):
        errors = validate_transaction(record)
        if isinstance(record, dict):
            if record.get("status", "completed") not in TRANSACTION_STATUSES:
                errors.append({"field": "status", "message": "Invalid status"})
            if "timestamp" in record:
                try:
                    parse_timestamp(record["timestamp"])
                except (TypeError, ValueError):
                    errors.append({"field": "timestamp", "message": "Invalid ISO 8601 timestamp"})
            if record.get("id") and store.get(record["id"]):
                errors.append({"field": "id", "message": "Duplicate id"})
        if errors:
            logger.warning("Skipping seed record #%d: %s", index, errors)
            continue
        store.add(Transaction.from_dict({**record, "amount": float(record["amount"])}))
        loaded += 1
    return loaded


if __name__ == "__main__":
    # Configure logging before create_app() so seed-loading messages show up.
    logging.basicConfig(level=logging.INFO)

app = create_app()

if __name__ == "__main__":
    app.run(
        host=os.environ.get("HOST", "127.0.0.1"),
        port=int(os.environ.get("PORT", "3000")),
        debug=os.environ.get("FLASK_DEBUG") == "1",
    )
