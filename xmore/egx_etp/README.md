# xmore.egx_etp

Production-grade EGX ETP ingestion module for the Xmore project.

Discovers, classifies, and stores the full live EGX ETP universe — ETFs,
structured products, index-tracking funds, gold-linked ETPs, and certificates.

**Conservative classification principle**: never invent issuer or exposure;
mark unknowns as `NULL`.

---

## Package structure

```
xmore/egx_etp/
├── __init__.py        public API re-exports
├── fetcher.py         HTTP + Playwright fallback fetcher with tenacity retries
├── parser.py          HTML parsers for each EGX page
├── classifier.py      ETP type classifier with confidence scores
├── models.py          dataclasses: ProductCard, HoldingRow, NavRecord, etc.
├── db.py              PostgreSQL/SQLite upserts + schema DDL
├── pipeline.py        Main orchestrator: daily incremental + backfill
├── backfill.py        One-off backfill script (run once)
├── schema.sql         Standalone PostgreSQL DDL with comments + indexes
└── README.md          This file
```

---

## Installation

```bash
pip install requests beautifulsoup4 lxml psycopg[binary] python-dotenv playwright tenacity
playwright install chromium
```

> **Note**: `playwright` is only required when EGX pages return JS-rendered
> shells that `requests` cannot parse. The fetcher falls back to Playwright
> automatically.

---

## Environment variables

| Variable       | Required | Default           | Description                            |
|---------------|----------|-------------------|----------------------------------------|
| `DATABASE_URL` | No       | —                 | PostgreSQL connection string (Render / local). If not set, falls back to SQLite at `./egx_etp.db`. |
| `RAW_DIR`      | No       | `./raw_pages`     | Directory for archived raw HTML files and run summaries. |
| `SQLITE_PATH`  | No       | `./egx_etp.db`    | SQLite path when `DATABASE_URL` is absent. |

Example `.env`:

```env
DATABASE_URL=postgresql://user:password@host:5432/dbname
RAW_DIR=/var/data/egx_etp/raw_pages
```

---

## Usage

### Run daily incremental ingestion

```bash
python -m xmore.egx_etp.pipeline
```

Or with explicit run-type:

```bash
python -m xmore.egx_etp.pipeline --run-type incremental
```

### Run one-off backfill (first time only)

```bash
python -m xmore.egx_etp.backfill
```

### Import in Python

```python
from xmore.egx_etp import run_daily

summary = run_daily()
print(summary["status"])           # 'success' or 'failed'
print(summary["cards_found"])      # number of ETP products found on EGX
print(summary["products_upserted"])
```

---

## Cron schedule (Africa/Cairo timezone)

EGX trading session: **09:00–14:00 Cairo (UTC+2)**, Sunday–Thursday.

| Cron (UTC)          | Cairo time | Days      | Job                  |
|--------------------|------------|-----------|----------------------|
| `30 12 * * 0-4`   | 14:30      | Sun–Thu   | Daily incremental    |

Add to GitHub Actions workflow (`.github/workflows/scheduled-tasks.yml`):

```yaml
  egx-etp-daily:
    name: EGX ETP daily ingestion
    runs-on: ubuntu-latest
    if: github.event_name == 'schedule'
    needs: []
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.11" }
      - run: pip install requests beautifulsoup4 lxml "psycopg[binary]" playwright tenacity
      - run: playwright install chromium --with-deps
      - run: python -m xmore.egx_etp.pipeline
        env:
          DATABASE_URL: ${{ secrets.DATABASE_URL }}
```

---

## EGX pages scraped

| Page key      | URL                                                    | Data extracted          |
|--------------|--------------------------------------------------------|-------------------------|
| `trading`    | https://www.egx.com.eg/en/ETFSPr.aspx                | Prices, NAV, prem/disc  |
| `holdings`   | https://www.egx.com.eg/en/FundConstituents.aspx       | Fund constituents       |
| `nav`        | https://www.egx.com.eg/en/NavUnit.aspx                | NAV unit values         |
| `volume`     | https://www.egx.com.eg/en/EtfFundVolume.aspx          | Volume, value           |
| `distribution`| https://www.egx.com.eg/en/funddistribution.aspx      | Fund distribution       |
| `bonds`      | https://www.egx.com.eg/en/ListedBonds.aspx            | Taxonomy reference      |
| `structured` | https://www.egx.com.eg/en/Structured_products.aspx    | Structured products taxonomy |

---

## Instrument types

| Type              | Classification rule                                               |
|------------------|-------------------------------------------------------------------|
| `ETF`            | Has fund constituents (holdings) and/or NAV unit data             |
| `GOLD_ETP`       | Name contains gold / ذهب / دهب                                    |
| `INDEX_TRACKER`  | Name references EGX30/EGX70/EGX100/index but no holdings         |
| `STRUCTURED_NOTE`| Bank/issuer-type naming + no holdings                             |
| `ETN`            | Found in structured products taxonomy, or synthetic without basket |
| `UNKNOWN_ETP`    | Insufficient evidence for any above category                      |

---

## Database schema

Six tables are created automatically by `ensure_schema()`:

- `etp_product` — master registry (one row per ETP code)
- `etp_market_snapshot` — daily OHLCV-equivalent (primary key: etp_id + date)
- `etp_holdings_snapshot` — header per fund-constituents extraction event
- `etp_holding_line` — one constituent per line per snapshot
- `raw_page_archive` — audit trail of every raw HTML file fetched
- `scrape_run_log` — one row per pipeline run for monitoring

See `schema.sql` for the full PostgreSQL DDL with comments.

---

## Raw page archive

Every fetched page is saved to `RAW_DIR` as:
- `<sha8>_<timestamp_utc>.html` — raw HTML
- `<sha8>_<timestamp_utc>.meta.json` — URL, method, timestamp

Run summaries are saved as `RAW_DIR/run_YYYY-MM-DD.json`.

---

## Idempotency

All database writes use `ON CONFLICT DO UPDATE` (PostgreSQL) or
`INSERT OR IGNORE` + `UPDATE` (SQLite). Running the pipeline multiple
times on the same day is safe.
