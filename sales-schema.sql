-- Normalized O2O sales schema for QC, PS, and TOL.
-- Source-specific headers are standardized to the canonical fields below.

CREATE TABLE sales_channels (
  channel_id INTEGER PRIMARY KEY,
  channel_name TEXT NOT NULL UNIQUE
);

CREATE TABLE ops_heads (
  ops_head_id INTEGER PRIMARY KEY,
  ops_head_name TEXT NOT NULL UNIQUE
);

CREATE TABLE stores (
  store_code TEXT PRIMARY KEY,
  store_name TEXT NOT NULL,
  ops_head_id INTEGER REFERENCES ops_heads(ops_head_id)
);

CREATE TABLE sales_transactions (
  transaction_id INTEGER PRIMARY KEY,
  channel_id INTEGER NOT NULL REFERENCES sales_channels(channel_id),
  store_code TEXT NOT NULL REFERENCES stores(store_code),
  transaction_date DATE NOT NULL,
  net_sales DECIMAL(18, 2) NOT NULL DEFAULT 0,
  orders DECIMAL(18, 3) NOT NULL DEFAULT 0,
  source_file TEXT NOT NULL CHECK (source_file IN ('qc-sales 2025.json_label', 'qc-sales 2026.json_label', 'QC-sales 2025-2026.json_label.json_label', 'ps-sales 2025-2026.json_label.xlsx', 'tol-sales 2025-2026.json_label.xlsx'))
);

CREATE INDEX idx_sales_transactions_date ON sales_transactions(transaction_date);
CREATE INDEX idx_sales_transactions_channel ON sales_transactions(channel_id);
CREATE INDEX idx_sales_transactions_store ON sales_transactions(store_code);
