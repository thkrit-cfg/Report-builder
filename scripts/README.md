# Auto-update ingestion

Place one ZIP per channel in its inbox folder:

```text
data/inbox/qc/QC-2026-09-09.zip
data/inbox/ps/PS-2026-09-09.zip
data/inbox/tol/TOL-2026-09-09.zip
```

Each ZIP must contain exactly one `.csv`. The channel is read from the inbox
folder or ZIP filename, and the CSV is mapped to the canonical fields:

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

The command creates or updates `data/db/o2o-sales.sqlite3`, records each ZIP
in `ingestion_batches`, ignores exact duplicate canonical rows, rebuilds the
local `sales-data.js`, and deletes only each successfully merged ZIP. It never
recursively deletes an inbox folder.

For a safe dry run of the cleanup behavior, keep the ZIPs:

```sh
python3 scripts/ingest_sales.py --keep-zips
```

Failed imports roll back and leave the ZIP in `data/inbox/`. The database,
logs, quarantine contents, and generated bundle are local and ignored by Git.
