#!/usr/bin/env python3
"""Build a local daily budget bundle from the O2O budget workbook."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
import calendar
from datetime import date
from pathlib import Path

from openpyxl import load_workbook


def month_from_path(path: Path) -> tuple[int, int]:
    match = re.search(r"date[_-](20\d{4})", path.stem)
    if not match:
        raise ValueError(f"Cannot determine YYYYMM from budget filename: {path.name}")
    value = match.group(1)
    return int(value[:4]), int(value[4:])


def parse_workbook(path: Path) -> list[dict[str, object]]:
    year, month = month_from_path(path)
    workbook = load_workbook(path, read_only=True, data_only=True)
    records = []
    for channel in ("QC", "PS", "TOL"):
        sheet = workbook[channel]
        days = [sheet.cell(3, column).value for column in range(6, 37)]
        values = [sheet.cell(5, column).value for column in range(6, 37)]
        for day, target in zip(days, values):
            if not isinstance(day, int) or day > calendar.monthrange(year, month)[1] or target is None:
                continue
            records.append({
                "channel": channel,
                "date": date(year, month, day).isoformat(),
                "target": float(target),
            })
    return records


def ensure_budget_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS sales_channels (
          channel_id INTEGER PRIMARY KEY,
          channel_name TEXT NOT NULL UNIQUE
        );
        CREATE TABLE IF NOT EXISTS budget_targets (
          target_id INTEGER PRIMARY KEY,
          channel_id INTEGER NOT NULL REFERENCES sales_channels(channel_id),
          target_date DATE NOT NULL,
          target_type TEXT NOT NULL DEFAULT 'Total LF',
          target_amount DECIMAL(18, 2) NOT NULL,
          source_file TEXT NOT NULL,
          source_sha256 TEXT NOT NULL,
          target_hash TEXT NOT NULL UNIQUE,
          merged_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_budget_targets_date ON budget_targets(target_date);
        CREATE INDEX IF NOT EXISTS idx_budget_targets_channel ON budget_targets(channel_id);
        """
    )


def merge_budget(connection: sqlite3.Connection, path: Path, records: list[dict[str, object]]) -> int:
    source_hash = hashlib.sha256(path.read_bytes()).hexdigest()
    inserted = 0
    for record in records:
        row = {**record, "target_type": "Total LF", "source_file": path.name, "source_sha256": source_hash}
        target_hash = hashlib.sha256(
            json.dumps(row, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        channel_id = connection.execute(
            "INSERT INTO sales_channels(channel_name) VALUES (?) ON CONFLICT(channel_name) DO UPDATE SET channel_name=excluded.channel_name RETURNING channel_id",
            (record["channel"],),
        ).fetchone()[0]
        result = connection.execute(
            """
            INSERT OR IGNORE INTO budget_targets
              (channel_id, target_date, target_type, target_amount, source_file, source_sha256, target_hash, merged_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
            """,
            (channel_id, record["date"], "Total LF", record["target"], path.name, source_hash, target_hash),
        )
        inserted += int(result.rowcount)
    return inserted


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, nargs="+", required=True)
    parser.add_argument("--output", type=Path, default=Path("budget-data.js"))
    parser.add_argument("--db", type=Path, default=Path("data/database/o2o-sales.sqlite3"))
    args = parser.parse_args()

    records_by_date: dict[tuple[str, str], dict[str, object]] = {}
    for path in args.input:
        for record in parse_workbook(path):
            records_by_date[(record["channel"], record["date"])] = record
    records = list(records_by_date.values())
    args.db.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(args.db)
    ensure_budget_schema(connection)
    with connection:
        inserted = sum(merge_budget(connection, path, parse_workbook(path)) for path in args.input)

    args.output.write_text(
        "window.O2O_BUDGET_DATA=" + json.dumps(records, separators=(",", ":")) + ";\n",
        encoding="utf-8",
    )
    connection.close()
    print(json.dumps({"rows": len(records), "inserted": inserted, "output": str(args.output), "database": str(args.db)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
