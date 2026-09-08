# Auto-update ingestion

Place all three daily ZIP files directly in the shared inbox:

```text
data/inbox/QC-2026-09-09.zip
data/inbox/PS-2026-09-09.zip
data/inbox/TOL-2026-09-09.zip
```

Each ZIP must contain exactly one `.csv`. The channel is read from the ZIP
filename (`QC`, `PS`, or `TOL`), and the CSV is mapped to the canonical fields:

```text
Sales Channel
Store Code
Store Name
Head of Ops
Transaction date
Net Sales
Orders
```

Run:

```sh
python3 scripts/ingest_sales.py
```

If the inbox is empty, the command initializes the blank SQLite database and
an empty `sales-data.js` bundle when they do not already exist. Existing
database and bundle contents are preserved.

The command creates or updates the local, ignored database
`data/database/o2o-sales.sqlite3`, records each ZIP
in `ingestion_batches`, ignores exact duplicate canonical rows, rebuilds the
local `sales-data.js`, and deletes only each successfully merged ZIP. It never
recursively deletes an inbox folder.

For a safe dry run of the cleanup behavior, keep the ZIPs:

```sh
python3 scripts/ingest_sales.py --keep-zips
```

Failed imports roll back and leave the ZIP in `data/inbox/`. The database,
logs, quarantine contents, and generated bundle are local and ignored by Git.

## Budget target bundle

Build the local August target bundle with:

```sh
python3 scripts/build_budget.py \
  --input "/path/to/O2O_budget by date_202608.xlsx" \
          "/path/to/O2O_budget by date_202609.xlsx" \
          "/path/to/O2O_budget by date_202610.xlsx"
```

This reads columns for days 1–31 from the `Total LF` row on the QC, PS, and
TOL sheets, merges them into the ignored
`data/database/o2o-sales.sqlite3` `budget_targets` table, and writes combined
ignored `budget-data.js`. The month is read from each filename’s `YYYYMM`
suffix.
