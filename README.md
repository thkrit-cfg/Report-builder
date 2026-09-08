# O2O Sales Dashboard

O2O covers three sales streams:

- **QC** — Quick Commerce
- **PS** — Personal Shopper
- **TOL** — Tops Online

The current local data bundle includes QC and PS data. TOL data can be added
using the same normalized transaction schema.

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
- `ps-sales 2025-2026.json_label.xlsx`
- generated `sales-data.js`

Open `sales-dashboard.html` after the local data bundle has been generated.
Do not commit raw sales data or `sales-data.js` to the public repository.
