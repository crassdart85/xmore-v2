# ETF Ingestion & RAG — Technical Specification

*Source: project owner specification, March 2026*

---

## 0) Source links (scraped by ingestion jobs)

### EGX (local ETFs)

| Page | URL |
|------|-----|
| ETF Trading Tape (daily OHLCV + trades + market cap) | https://www.egx.com.eg/en/ETFSPr.aspx |
| ETF NAV Unit (NAV + last update date) | https://www.egx.com.eg/en/NavUnit.aspx |
| ETF Fund Constituents (holdings/weights + last update date) | https://www.egx.com.eg/en/FundConstituents.aspx |
| ETF Fund Volume (fund size, net subs, no. units + last update date) | https://www.egx.com.eg/en/EtfFundVolume.aspx |
| ETF Fund Distribution (dividends; often empty but keep pipeline ready) | https://www.egx.com.eg/en/funddistribution.aspx |
| ETF iNAV / Tracking Error | https://www.egx.com.eg/en/ETFINAV_Err.aspx |

### EGX30 ETF docs
- EGX30 ETF Information Sheet (PDF): https://www.egx30etf.com/Content/PDF%20Files/EGX30%20ETF%20Information%20Sheet.pdf

### Global "Egypt exposure" ETF universe

| Resource | URL |
|----------|-----|
| ETFDB – ETFs with Egypt Exposure | https://etfdb.com/country/egypt/ |
| ETFDB – Country exposure tool | https://etfdb.com/tool/etf-country-exposure-tool/ |
| EGPT holdings (Yahoo Finance) | https://finance.yahoo.com/quote/EGPT/holdings/ |
| FM holdings (Yahoo Finance UK) | https://uk.finance.yahoo.com/quote/FM/holdings/ |
| VanEck EGPT prospectus library | https://www.vaneck.com/us/en/library/market-vectors-etfs/egpt-statutory-prospectus-pdf/ |
| SEC EDGAR EGPT filing index | https://www.sec.gov/Archives/edgar/data/1137360/000113736024000170/0001137360-24-000170-index.htm |

---

## 1) Operating assumptions

- **EGX trading hours** (Africa/Cairo): 10:30–14:30, Mon–Fri
- **Global ETFs**: end-of-day snapshot after US markets close (no live tracking initially)

---

## 2) Database schema (Postgres DDL)

```sql
-- =========================
--  ENUMS
-- =========================
DO $$ BEGIN
  CREATE TYPE instrument_type AS ENUM ('EQUITY', 'ETF', 'INDEX', 'FX', 'RATE');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE TYPE exchange_code AS ENUM ('EGX', 'NYSE', 'NASDAQ', 'LSE', 'XETRA', 'TSX', 'OTHER');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE TYPE currency_code AS ENUM ('EGP', 'USD', 'EUR', 'GBP', 'CAD', 'OTHER');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE TYPE etf_region AS ENUM ('LOCAL_EGX', 'GLOBAL');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE TYPE doc_type AS ENUM ('PROSPECTUS', 'FACTSHEET', 'INFO_SHEET', 'INDEX_METHODOLOGY', 'HOLDINGS_FILE', 'OTHER');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

-- =========================
--  INSTRUMENT MASTER
-- =========================
CREATE TABLE IF NOT EXISTS instrument (
  instrument_id       BIGSERIAL PRIMARY KEY,
  type                instrument_type NOT NULL,
  region              etf_region,
  symbol              TEXT NOT NULL,
  isin                TEXT,
  name                TEXT,
  exchange            exchange_code,
  currency            currency_code,
  country             TEXT,
  issuer              TEXT,
  underlying_index    TEXT,
  inception_date      DATE,
  is_active           BOOLEAN NOT NULL DEFAULT TRUE,
  created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (exchange, symbol)
);

CREATE INDEX IF NOT EXISTS idx_instrument_type ON instrument(type);
CREATE INDEX IF NOT EXISTS idx_instrument_symbol ON instrument(symbol);

CREATE TABLE IF NOT EXISTS instrument_alias (
  instrument_alias_id BIGSERIAL PRIMARY KEY,
  instrument_id       BIGINT NOT NULL REFERENCES instrument(instrument_id) ON DELETE CASCADE,
  alias               TEXT NOT NULL,
  alias_type          TEXT NOT NULL DEFAULT 'GENERAL',
  UNIQUE (instrument_id, alias)
);

-- =========================
--  EGX ETF TRADING TAPE (DAILY)
-- =========================
CREATE TABLE IF NOT EXISTS etf_price_daily (
  instrument_id   BIGINT NOT NULL REFERENCES instrument(instrument_id) ON DELETE CASCADE,
  trade_date      DATE NOT NULL,
  open_price      NUMERIC(18,6),
  high_price      NUMERIC(18,6),
  low_price       NUMERIC(18,6),
  close_price     NUMERIC(18,6),
  last_price      NUMERIC(18,6),
  pct_change      NUMERIC(12,6),
  value_traded    NUMERIC(24,6),
  volume          NUMERIC(24,6),
  trades          INTEGER,
  market_cap_mn   NUMERIC(24,6),
  source_url      TEXT NOT NULL,
  ingested_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (instrument_id, trade_date)
);

-- =========================
--  NAV / iNAV / Premium-Discount
-- =========================
CREATE TABLE IF NOT EXISTS etf_nav (
  instrument_id    BIGINT NOT NULL REFERENCES instrument(instrument_id) ON DELETE CASCADE,
  nav_date         DATE NOT NULL,
  nav_value        NUMERIC(18,6) NOT NULL,
  last_update_raw  TEXT,
  source_url       TEXT NOT NULL,
  ingested_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (instrument_id, nav_date)
);

CREATE TABLE IF NOT EXISTS etf_inav (
  instrument_id   BIGINT NOT NULL REFERENCES instrument(instrument_id) ON DELETE CASCADE,
  ts              TIMESTAMPTZ NOT NULL,
  inav_value      NUMERIC(18,6),
  tracking_error  NUMERIC(18,6),
  source_url      TEXT NOT NULL,
  ingested_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (instrument_id, ts)
);

CREATE TABLE IF NOT EXISTS etf_premium_discount_daily (
  instrument_id      BIGINT NOT NULL REFERENCES instrument(instrument_id) ON DELETE CASCADE,
  asof_date          DATE NOT NULL,
  market_price       NUMERIC(18,6) NOT NULL,
  nav_value          NUMERIC(18,6) NOT NULL,
  premium_discount   NUMERIC(18,6) NOT NULL,
  nav_date_used      DATE NOT NULL,
  calc_notes         TEXT,
  created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (instrument_id, asof_date)
);

-- =========================
--  EGX ETF FUND VOLUME
-- =========================
CREATE TABLE IF NOT EXISTS etf_fund_volume (
  instrument_id     BIGINT NOT NULL REFERENCES instrument(instrument_id) ON DELETE CASCADE,
  asof_date         DATE NOT NULL,
  fund_size         NUMERIC(24,6),
  net_subs          NUMERIC(24,6),
  no_units          NUMERIC(24,6),
  last_update_raw   TEXT,
  source_url        TEXT NOT NULL,
  ingested_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (instrument_id, asof_date)
);

-- =========================
--  HOLDINGS SNAPSHOTS
-- =========================
CREATE TABLE IF NOT EXISTS etf_holdings_snapshot (
  snapshot_id      BIGSERIAL PRIMARY KEY,
  instrument_id    BIGINT NOT NULL REFERENCES instrument(instrument_id) ON DELETE CASCADE,
  snapshot_date    DATE NOT NULL,
  source           TEXT NOT NULL,
  source_url       TEXT NOT NULL,
  currency         currency_code,
  total_weight     NUMERIC(18,8),
  ingested_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (instrument_id, snapshot_date, source)
);

CREATE TABLE IF NOT EXISTS etf_holding_line (
  snapshot_id      BIGINT NOT NULL REFERENCES etf_holdings_snapshot(snapshot_id) ON DELETE CASCADE,
  line_no          INTEGER NOT NULL,
  holding_symbol   TEXT,
  holding_name     TEXT NOT NULL,
  holding_isin     TEXT,
  weight_pct       NUMERIC(18,10) NOT NULL,
  country          TEXT,
  sector           TEXT,
  asset_type       TEXT,
  PRIMARY KEY (snapshot_id, line_no)
);
CREATE INDEX IF NOT EXISTS idx_holding_line_symbol ON etf_holding_line(holding_symbol);

-- =========================
--  COUNTRY EXPOSURE
-- =========================
CREATE TABLE IF NOT EXISTS etf_country_exposure (
  instrument_id    BIGINT NOT NULL REFERENCES instrument(instrument_id) ON DELETE CASCADE,
  asof_date        DATE NOT NULL,
  country          TEXT NOT NULL,
  weight_pct       NUMERIC(18,10) NOT NULL,
  source_url       TEXT NOT NULL,
  ingested_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (instrument_id, asof_date, country)
);

-- =========================
--  RAG DOCS METADATA
-- =========================
CREATE TABLE IF NOT EXISTS rag_document (
  doc_id           BIGSERIAL PRIMARY KEY,
  instrument_id    BIGINT REFERENCES instrument(instrument_id) ON DELETE SET NULL,
  doc_type         doc_type NOT NULL,
  title            TEXT NOT NULL,
  publisher        TEXT,
  language         TEXT,
  publish_date     DATE,
  url              TEXT NOT NULL,
  content_hash     TEXT,
  storage_uri      TEXT,
  fetched_at       TIMESTAMPTZ,
  ingested_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (url)
);

CREATE TABLE IF NOT EXISTS rag_embedding_job (
  job_id           BIGSERIAL PRIMARY KEY,
  doc_id           BIGINT NOT NULL REFERENCES rag_document(doc_id) ON DELETE CASCADE,
  embed_model      TEXT NOT NULL DEFAULT 'text-embedding-004',
  status           TEXT NOT NULL DEFAULT 'PENDING',
  started_at       TIMESTAMPTZ,
  finished_at      TIMESTAMPTZ,
  error_message    TEXT
);
```

---

## 3) Ingestion jobs

| Job | Source | Output table |
|-----|--------|-------------|
| `egx_etf_tape` | ETFSPr.aspx | `etf_price_daily` |
| `egx_etf_nav` | NavUnit.aspx | `etf_nav` |
| `egx_etf_holdings` | FundConstituents.aspx | `etf_holdings_snapshot` + `etf_holding_line` |
| `egx_etf_fund_volume` | EtfFundVolume.aspx | `etf_fund_volume` |
| `etf_premium_discount_compute` | SQL join | `etf_premium_discount_daily` |
| `global_etf_universe_refresh` | ETFDB + seed | `instrument` + `etf_country_exposure` |
| `global_etf_prices_daily` | ETFDB → yfinance | `etf_price_daily` |
| `global_etf_holdings_refresh` | Yahoo Finance | `etf_holdings_snapshot` + `etf_holding_line` |
| `etf_docs_ingest` | PDF URLs | `rag_document` + `rag_embedding_job` |
| `rag_embedding_worker` | DB queue | `rag_chunks` |

### EGX scraping notes
- Pages are ASP.NET WebForms; use `requests` + `BeautifulSoup`
- Normalize numbers: strip commas, handle empty cells
- Some pages may intermittently return "Request Rejected" → catch gracefully, log, retry

---

## 4) Cron schedule (all UTC, Africa/Cairo = UTC+2)

```
# EGX post-close jobs (Mon–Fri)
35 12 * * 1-5   python -m engines.etf_egx_tape
45 12 * * 1-5   python -m engines.etf_egx_nav
0  13 * * 1-5   python -m engines.etf_egx_holdings
10 13 * * 1-5   python -m engines.etf_egx_fund_volume
20 13 * * 1-5   python -m engines.etf_premium_discount

# Global ETF prices (Mon–Fri)
30 21 * * 1-5   python -m engines.etf_global_prices
30  4 * * 1-5   python -m engines.etf_global_prices --backfill

# Weekly refresh (Sunday)
0  5 * * 0      python -m engines.etf_global_universe
30 5 * * 0      python -m engines.etf_global_holdings
0  6 * * 0      python -m engines.etf_docs_ingest

# Hourly embedding worker
15 * * * *      python -m engines.etf_rag_embedding_worker
```

---

## 5) RAG prompts (production-grade templates)

### 5.1 System prompt
```
You are Xmore ETF Intelligence, an institutional research assistant for EGX and global Egypt-exposure ETFs.

Non-negotiables:
- Never invent numbers. If a requested figure is not present in retrieved sources, say "Not available in the retrieved data."
- Always distinguish: Market Price vs NAV vs iNAV. Never treat them as interchangeable.
- Every numeric claim MUST cite its source (URL + as-of date).
- If NAV is stale (older than 7 calendar days), warn clearly: "Latest NAV is dated YYYY-MM-DD."

You can answer:
- ETF price action, liquidity (value, volume, trades)
- NAV and premium/discount
- Holdings / constituents (with snapshot date)
- Fees / objective / structure from prospectus/factsheets
- Egypt exposure weight for global ETFs (country exposure)

Output format:
1) Direct answer (2–6 bullet points)
2) Key numbers table (only if data exists)
3) Sources (bullets with URLs and as-of dates)
4) Data gaps / warnings (if any)
```

### 5.2 Retrieval routing
```
Classify the user question into one or more intents:
- PRICE_ACTION: wants market prices, volume, trades, performance
- NAV_FAIR_VALUE: wants NAV, iNAV, premium/discount, tracking error
- HOLDINGS: wants constituents/weights, sector/country breakdown
- FEES_STRUCTURE: wants expense ratio, creation/redemption, prospectus language
- EGYPT_EXPOSURE: wants Egypt weight for global ETFs
- DOC_QA: wants info sheet/prospectus/factsheet specifics
```

### 5.3 Premium/discount formula
```
premium_discount = (market_price - nav_value) / nav_value

Always show nav_date_used. Warn if NAV date ≠ market date.
```

---

## 6) Implementation (engines/ directory)

```
engines/
  etf_shared.py           — DB helpers, EgxScraper, get_or_create_instrument
  etf_egx_tape.py         — ETFSPr.aspx → etf_price_daily
  etf_egx_nav.py          — NavUnit.aspx → etf_nav
  etf_egx_holdings.py     — FundConstituents.aspx → holdings snapshot
  etf_egx_fund_volume.py  — EtfFundVolume.aspx → etf_fund_volume
  etf_premium_discount.py — SQL compute → etf_premium_discount_daily
  etf_global_universe.py  — ETFDB + seed → instrument + country_exposure
  etf_global_prices.py    — ETFDB/yfinance → etf_price_daily
  etf_global_holdings.py  — Yahoo Finance → holdings snapshot
  etf_docs_ingest.py      — PDF download → rag_document + rag_embedding_job
  etf_rag_embedding_worker.py — PENDING jobs → rag_chunks
```

---

## 7) Practical warnings

- **EGX scraping**: Some pages may block automated requests. Handle "Request Rejected" gracefully; log and skip rather than crash.
- **ETFDB**: May return 403/429. Always fall back to the hardcoded seed list.
- **yfinance**: Occasionally returns empty DataFrames for tickers outside US markets. Validate before inserting.
- **PDF downloads**: Some issuers rotate PDF URLs. Use `content_hash` to detect duplicates.
