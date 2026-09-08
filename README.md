# O2O Sales Dashboard

O2O covers three sales streams:

- **QC** — Quick Commerce
- **PS** — Personal Shopper
- **TOL** — Tops Online

The current local data bundle includes QC, PS, and TOL data using the same
normalized transaction schema.

## Canonical sales fields

Source headers are standardized as follows:

| Canonical field | QC source | PS source | TOL source |
|---|---|---|---|
| Channel identifier | `Sales Channel` | Keep channel identifier as-is | Keep channel identifier as-is |
| Store Code | `Store Code` | `Store Code` | Cleaned to `Store Code` |
| Store Name | `Store Name` | `Store Name` | `Store Name` |
| Head of Ops | `Head of Ops` | `Head of Ops` | `Area Rm` renamed to `Head of Ops` |
| Transaction date | `Transaction Date` | `Transaction Date` | `Transaction Date` |
| Net Sales | `Net Sales` | `Net Sales` | `Net Sales` |
| Orders | `Orders` | `Total Transactions` mapped to `Orders` | `Orders` |

Source row indexes are not part of the normalized structure.

## Copilot

The dashboard includes a local view assistant that works without credentials
and can change filters, date presets, trend granularity, and labels. If an n8n
middleware webhook is configured in the HTML, requests use that backend
instead.

This repository contains the dashboard UI and database schema. Sales source
files and the generated browser data bundle are intentionally kept local and
are excluded by `.gitignore`.

## Local setup

Keep these files in the project folder:

- `qc-sales 2025.json_label`
- `qc-sales 2026.json_label`
- `QC-sales 2025-2026.json_label.json_label`
- `ps-sales 2025-2026.json_label.xlsx`
- generated `sales-data.js`

Open `sales-dashboard.html` after the local data bundle has been generated.
Do not commit raw sales data or `sales-data.js` to the public repository.
