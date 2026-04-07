# Xmore — Project Guidelines

Automated trading-signal platform currently running a **KSA-first Tadawul deployment** on the shared Xmore codebase. The multi-agent system generates 5-day predictions, evaluates performance, and serves results via a Node.js web UI and Streamlit dashboard.

## Stack

| Layer | Tech |
|-------|------|
| Signal pipeline | Python 3.10 — pandas, scikit-learn, LightGBM, Optuna, EODHD, yfinance |
| Sentiment | Google Gemini, VADER, TextBlob |
| Database | SQLite (local `stocks.db`) / PostgreSQL (production via `DATABASE_URL`) |
| Web backend | Node.js + Express (`web-ui/`) |
| Web frontend | Vanilla JS modules (`web-ui/public/`) — no React/Vue |
| Dashboard | Streamlit (`dashboard.py`) |
| CI/CD | GitHub Actions (`.github/workflows/scheduled-tasks.yml`) — KSA/Tadawul workflows with some legacy Tadawul jobs still present in the repo |
| Hosting | Render (`render.yaml`) and Vercel (`vercel.json`) |

## Build & Run

```bash
# Python environment
pip install -r requirements.txt
python database.py            # init schema

# Full pipeline (collect → train → agents → evaluate)
python run_pipeline.py

# Individual steps
python collect_data.py        # prices + news (--prices-only for prices)
python train_model.py
python run_agents.py          # generate signals
python evaluate.py            # score predictions (--lookback --days 7)

# Web UI
cd web-ui && npm install && node server.js

# Streamlit dashboard
streamlit run dashboard.py
```

## Tests

```bash
pytest tests/
```

Test files live in `tests/` and cover portfolio, backtest, metrics, and formatting.

## Architecture

```
agents/          Signal agents (inherit BaseAgent) + consensus + evaluators
engines/         ETF signals, backtesting, briefing, performance, circuit breaker,
                 agent_weights, event_detector, job_locks, macro_data, regime_model
openbb_egx/      OpenBB-compatible Tadawul data provider (legacy module name; Pydantic v2, async TradingView + yfinance)
web-ui/          Express API + vanilla JS frontend (routes/, public/, services/)
web-ui/services/ openbbMcpBridge.js — MCP bridge for RAG chat live data enrichment
xmore_data/      Market-data provider layer (KSA-first Tadawul, legacy EGX provider retained)
xmore_news/      News ingestion pipelines
xmore_sentiment/ Sentiment analysis (Gemini, VADER, TextBlob)
models/          Trained ML models (.joblib)
migrations/      DB schema versioning (013–015: agent weights, eval metrics, job locks)
                 Note: confidence_score (predictions) and is_simulated (trade_recommendations)
                 are auto-applied via _safe_add_column() in database.py create_tables()
config/          Execution configuration + ksa_universe.py (stock universe) + ksa_holidays.py (trading calendar)
```

## Key Conventions

### Agent pattern
All agents inherit `BaseAgent` from `agents/agent_base.py` and return `AgentSignal` objects with: `agent_name`, `symbol`, `prediction` ("UP"/"DOWN"/"HOLD"), `confidence` (0–100), `reasoning` dict, `timestamp`.

### Database
- `database.py` provides `get_connection()` context manager for safe connections.
- Cross-DB: auto-converts SQLite `?` placeholders to PostgreSQL `%s`.
- Never use raw string interpolation for SQL — always parameterized queries.

### KSA market awareness
- Tadawul trades **Sun–Thu, 10:00–15:00 Riyadh** (07:00–12:00 UTC).
- The active KSA deployment uses `.SR` symbols (e.g., `2222.SR`).
- Trading calendar: `config/ksa_holidays.py` provides `is_trading_day()`, shared by `run_agents_ksa.py`.
- Some legacy DB table/column names retained for schema compatibility: `egx30_stocks` (holds `.SR` rows), `round_trip_cost_egp` (holds SAR values), `egx30_return_pct` (holds TASI benchmark).
- Macro feature: `MACRO_USDSAR` / `usdsar_close` / `usdsar_return_5d` (not USDEGP).
- Regime proxy: `TASI.INDX`, `^TASI`, `2222.SR` (not EGX30.CA).
- RSS feeds: 9 Saudi/GCC sources (not Egyptian feeds).
- Sentiment: `KSA_TOP50` from `config.ksa_universe` (not `EGX_SYMBOL_DATABASE`).

### Environment variables
`DATABASE_URL`, `EODHD_API_KEY`, `NEWS_API_KEY`, `FINNHUB_API_KEY`, `GOOGLE_API_KEY`, `TELEGRAM_API_ID`, `TELEGRAM_API_HASH`. See `.env.example` for the full list.

### Config
`config.py` currently exports the KSA/Tadawul universe as the active runtime list while retaining `EGX_STOCKS` as a compatibility alias for older modules.

### Web routes
- Route files use `STOCK_TABLE` constant (defaults to `'egx30_stocks'` — legacy table name) for DB queries.
- All queries filter `WHERE symbol LIKE '%.SR'` to scope to KSA data.
- `ksa-track-record.js` uses DB-dialect-aware casts for SQLite/PostgreSQL parity.

## Pitfalls

- **Dual DB mode**: Code must work with both SQLite and PostgreSQL — test placeholder conversion when writing new queries.
- **KSA provider precedence**: Tadawul workflows should set `EODHD_API_KEY` so EODHD remains the primary KSA source; without it, jobs fall back to yfinance.
- **yfinance rate limits**: Batch symbol lookups where possible; add retries on `HTTPError`.
- **Gemini API quotas**: `gemini_agent.py` and `sentiment_gemini.py` share the same `GOOGLE_API_KEY` quota.
- **Stale evaluations**: After schema changes, run `fix_stale_evaluations.py` to backfill missing fields.
