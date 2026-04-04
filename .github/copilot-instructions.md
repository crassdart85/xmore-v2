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
| CI/CD | GitHub Actions (`.github/workflows/scheduled-tasks.yml`) — KSA/Tadawul workflows with some legacy EGX jobs still present in the repo |
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
openbb_egx/      OpenBB-compatible EGX data provider (Pydantic v2, async TradingView + yfinance)
web-ui/          Express API + vanilla JS frontend (routes/, public/, services/)
web-ui/services/ openbbMcpBridge.js — MCP bridge for RAG chat live data enrichment
xmore_data/      Market-data provider layer (KSA-first Tadawul, legacy EGX support)
xmore_news/      News ingestion pipelines
xmore_sentiment/ Sentiment analysis (Gemini, VADER, TextBlob)
models/          Trained ML models (.joblib)
migrations/      DB schema versioning (013–015: agent weights, eval metrics, job locks)
config/          Execution configuration
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
- Some legacy modules and table names still retain EGX naming for compatibility.

### Environment variables
`DATABASE_URL`, `EODHD_API_KEY`, `NEWS_API_KEY`, `FINNHUB_API_KEY`, `GOOGLE_API_KEY`, `TELEGRAM_API_ID`, `TELEGRAM_API_HASH`. See `.env.example` for the full list.

### Config
`config.py` currently exports the KSA/Tadawul universe as the active runtime list while retaining `EGX_STOCKS` as a compatibility alias for older modules.

## Pitfalls

- **Dual DB mode**: Code must work with both SQLite and PostgreSQL — test placeholder conversion when writing new queries.
- **KSA provider precedence**: Tadawul workflows should set `EODHD_API_KEY` so EODHD remains the primary KSA source; without it, jobs fall back to yfinance.
- **yfinance rate limits**: Batch symbol lookups where possible; add retries on `HTTPError`.
- **Gemini API quotas**: `gemini_agent.py` and `sentiment_gemini.py` share the same `GOOGLE_API_KEY` quota.
- **Stale evaluations**: After schema changes, run `fix_stale_evaluations.py` to backfill missing fields.
