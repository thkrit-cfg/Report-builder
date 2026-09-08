#!/usr/bin/env python3
"""Merge channel CSV ZIP drops into the local O2O SQLite database."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import sqlite3
import zipfile
from datetime import datetime, timezone
from pathlib import Path


CHANNELS = {"qc": "QC", "ps": "PS", "tol": "TOL"}
ALIASES = {
    "channel": ("channel identifier", "sales channel", "channel"),
    "store_code": ("store code", "code"),
    "store_name": ("store name", "store"),
    "ops": ("head of ops", "area rm", "ops head"),
    "date": ("transaction date", "transaction date date", "date"),
    "net_sales": ("net sales", "total net sales amount", "net sales amount"),
    "orders": ("orders", "total quantity", "total transactions", "order quantity"),
}


def normalize_header(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower().replace("_", " "))


def find_column(headers: list[str], names: tuple[str, ...], required: bool = True) -> str | None:
    normalized = {normalize_header(header): header for header in headers}
    for name in names:
        if name in normalized:
            return normalized[name]
    if required:
        raise ValueError(f"Missing required CSV column; expected one of: {', '.join(names)}")
    return None


def numeric(value: str | None) -> float:
    return float(str(value or "").replace(",", "").strip() or 0)


def clean(value: str | None, fallback: str = "") -> str:
    return str(value or "").strip() or fallback


def canonical_row(raw: dict[str, str], channel: str) -> dict[str, object]:
    headers = list(raw)
    channel_column = find_column(headers, ALIASES["channel"], required=False)
    code_column = find_column(headers, ALIASES["store_code"])
    name_column = find_column(headers, ALIASES["store_name"])
    ops_column = find_column(headers, ALIASES["ops"], required=False)
    date_column = find_column(headers, ALIASES["date"])
    sales_column = find_column(headers, ALIASES["net_sales"])
    orders_column = find_column(headers, ALIASES["orders"])
    return {
        "channel": clean(raw.get(channel_column) if channel_column else channel),
        "store_code": clean(raw.get(code_column)),
        "store_name": clean(raw.get(name_column)),
        "ops": clean(raw.get(ops_column), "closed") if ops_column else "closed",
        "date": clean(raw.get(date_column)),
        "net_sales": numeric(raw.get(sales_column)),
        "orders": numeric(raw.get(orders_column)),
    }


def row_hash(row: dict[str, object]) -> str:
    payload = json.dumps(row, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def channel_from_name(path: Path) -> str:
    name = "/".join(part.lower() for part in path.parts)
    for key, channel in CHANNELS.items():
        if re.search(rf"(^|[^a-z]){key}([^a-z]|$)", name):
            return channel
    raise ValueError(f"Cannot determine channel from ZIP filename: {path.name}; include QC, PS, or TOL")


def schema_sql() -> str:
    return """
    PRAGMA foreign_keys = ON;
    CREATE TABLE IF NOT EXISTS sales_channels (
      channel_id INTEGER PRIMARY KEY,
      channel_name TEXT NOT NULL UNIQUE
    );
    CREATE TABLE IF NOT EXISTS ops_heads (
      ops_head_id INTEGER PRIMARY KEY,
      ops_head_name TEXT NOT NULL UNIQUE
    );
    CREATE TABLE IF NOT EXISTS stores (
      store_code TEXT PRIMARY KEY,
      store_name TEXT NOT NULL,
      ops_head_id INTEGER REFERENCES ops_heads(ops_head_id)
    );
    CREATE TABLE IF NOT EXISTS ingestion_batches (
      batch_id TEXT PRIMARY KEY,
      channel_name TEXT NOT NULL,
      zip_name TEXT NOT NULL,
      zip_sha256 TEXT NOT NULL UNIQUE,
      row_count INTEGER NOT NULL,
      inserted_count INTEGER NOT NULL,
      duplicate_count INTEGER NOT NULL,
      merged_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS sales_transactions (
      transaction_id INTEGER PRIMARY KEY,
      channel_id INTEGER NOT NULL REFERENCES sales_channels(channel_id),
      store_code TEXT NOT NULL REFERENCES stores(store_code),
      transaction_date DATE NOT NULL,
      net_sales DECIMAL(18, 2) NOT NULL DEFAULT 0,
      orders DECIMAL(18, 3) NOT NULL DEFAULT 0,
      record_hash TEXT NOT NULL UNIQUE,
      source_batch_id TEXT NOT NULL REFERENCES ingestion_batches(batch_id)
    );
    CREATE INDEX IF NOT EXISTS idx_sales_transactions_date ON sales_transactions(transaction_date);
    CREATE INDEX IF NOT EXISTS idx_sales_transactions_channel ON sales_transactions(channel_id);
    CREATE INDEX IF NOT EXISTS idx_sales_transactions_store ON sales_transactions(store_code);
    """


def read_zip(path: Path, channel: str) -> list[dict[str, object]]:
    with zipfile.ZipFile(path) as archive:
        csv_names = [name for name in archive.namelist() if name.lower().endswith(".csv")]
        if len(csv_names) != 1:
            raise ValueError(f"{path.name} must contain exactly one CSV file; found {len(csv_names)}")
        with archive.open(csv_names[0]) as source:
            text = io.TextIOWrapper(source, encoding="utf-8-sig", newline="")
            return [canonical_row(row, channel) for row in csv.DictReader(text)]


def write_bundle(connection: sqlite3.Connection, output: Path) -> int:
    rows = connection.execute(
        """
        SELECT c.channel_name, s.store_code, s.store_name, o.ops_head_name,
               t.transaction_date, t.net_sales, t.orders
        FROM sales_transactions t
        JOIN sales_channels c ON c.channel_id = t.channel_id
        JOIN stores s ON s.store_code = t.store_code
        LEFT JOIN ops_heads o ON o.ops_head_id = s.ops_head_id
        ORDER BY t.transaction_date, t.transaction_id
        """
    ).fetchall()
    records = [
        {
            "Sales Channel": row[0],
            "Store Code": row[1],
            "Store Name": row[2],
            "Head of Ops": row[3] or "closed",
            "Transaction date": row[4],
            "Net Sales": row[5],
            "Orders": row[6],
        }
        for row in rows
    ]
    output.write_text(
        "window.QC_SALES_DATA=" + json.dumps(records, separators=(",", ":"), ensure_ascii=False) + ";\n",
        encoding="utf-8",
    )
    return len(records)


def merge_zip(connection: sqlite3.Connection, path: Path) -> tuple[int, int, str]:
    raw_bytes = path.read_bytes()
    zip_hash = hashlib.sha256(raw_bytes).hexdigest()
    existing = connection.execute(
        "SELECT batch_id FROM ingestion_batches WHERE zip_sha256 = ?", (zip_hash,)
    ).fetchone()
    if existing:
        return 0, 0, existing[0]

    channel = channel_from_name(path)
    rows = read_zip(path, channel)
    batch_id = f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{zip_hash[:12]}"
    connection.execute(
        """
        INSERT INTO ingestion_batches
          (batch_id, channel_name, zip_name, zip_sha256, row_count, inserted_count, duplicate_count, merged_at)
        VALUES (?, ?, ?, ?, ?, 0, 0, ?)
        """,
        (batch_id, channel, path.name, zip_hash, len(rows), datetime.now(timezone.utc).isoformat()),
    )
    inserted = 0
    duplicates = 0
    for row in rows:
        digest = row_hash(row)
        channel_id = connection.execute(
            "INSERT INTO sales_channels(channel_name) VALUES (?) ON CONFLICT(channel_name) DO UPDATE SET channel_name=excluded.channel_name RETURNING channel_id",
            (row["channel"],),
        ).fetchone()[0]
        ops_id = connection.execute(
            "INSERT INTO ops_heads(ops_head_name) VALUES (?) ON CONFLICT(ops_head_name) DO UPDATE SET ops_head_name=excluded.ops_head_name RETURNING ops_head_id",
            (row["ops"],),
        ).fetchone()[0]
        connection.execute(
            """
            INSERT INTO stores(store_code, store_name, ops_head_id)
            VALUES (?, ?, ?)
            ON CONFLICT(store_code) DO UPDATE SET
              store_name=excluded.store_name,
              ops_head_id=excluded.ops_head_id
            """,
            (row["store_code"], row["store_name"], ops_id),
        )
        result = connection.execute(
            """
            INSERT OR IGNORE INTO sales_transactions
              (channel_id, store_code, transaction_date, net_sales, orders, record_hash, source_batch_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (channel_id, row["store_code"], row["date"], row["net_sales"], row["orders"], digest, batch_id),
        )
        if result.rowcount:
            inserted += 1
        else:
            duplicates += 1

    connection.execute(
        """
        UPDATE ingestion_batches
        SET inserted_count = ?, duplicate_count = ?, merged_at = ?
        WHERE batch_id = ?
        """,
        (inserted, duplicates, datetime.now(timezone.utc).isoformat(), batch_id),
    )
    return inserted, duplicates, batch_id


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--keep-zips", action="store_true", help="Do not delete ZIP files after a successful merge")
    parser.add_argument("--no-bundle", action="store_true", help="Do not rebuild sales-data.js")
    args = parser.parse_args()

    root = args.root.resolve()
    inbox = root / "data" / "inbox"
    db_path = root / "data" / "database" / "o2o-sales.sqlite3"
    bundle_path = root / "sales-data.js"
    for path in (inbox, root / "data" / "logs", root / "data" / "quarantine", db_path.parent):
        path.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(db_path)
    connection.executescript(schema_sql())
    zips = sorted(inbox.glob("*.zip"))
    if not zips:
        bundle_rows = None
        if not args.no_bundle and not bundle_path.exists():
            bundle_rows = write_bundle(connection, bundle_path)
        connection.close()
        print(json.dumps({
            "database": str(db_path),
            "batches": [],
            "bundle_rows": bundle_rows,
            "message": "No ZIP files found; initialized blank local data stores." if bundle_rows == 0 else "No ZIP files found; existing data preserved.",
        }, indent=2))
        return 0

    summaries = []
    try:
        with connection:
            for path in zips:
                inserted, duplicates, batch_id = merge_zip(connection, path)
                summaries.append({"zip": path.name, "inserted": inserted, "duplicates": duplicates, "batch_id": batch_id})
            if not args.no_bundle:
                bundle_rows = write_bundle(connection, bundle_path)
        if not args.keep_zips:
            for path in zips:
                path.unlink()
    except Exception:
        connection.close()
        raise
    finally:
        connection.close()

    print(json.dumps({"database": str(db_path), "batches": summaries, "bundle_rows": bundle_rows if not args.no_bundle else None}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
