# Xmore — Project Guidelines

Automated trading-signal platform for the **Egyptian Exchange (EGX)**. Multi-agent system generates 5-day predictions, evaluates performance, and serves results via a Node.js web UI and Streamlit dashboard.

## Stack

| Layer | Tech |
|-------|------|
| Signal pipeline | Python 3.10 — pandas, scikit-learn, LightGBM, Optuna, yfinance |
| Sentiment | Google Gemini, VADER, TextBlob |
| Database | SQLite (local `stocks.db`) / PostgreSQL (production via `DATABASE_URL`) |
| Web backend | Node.js + Express (`web-ui/`) |
| Web frontend | Vanilla JS modules (`web-ui/public/`) — no React/Vue |
| Dashboard | Streamlit (`dashboard.py`) |
| CI/CD | GitHub Actions (`.github/workflows/scheduled-tasks.yml`) — cron aligned to EGX hours |
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
engines/         ETF signals, backtesting, briefing, performance, circuit breaker
web-ui/          Express API + vanilla JS frontend (routes/, public/)
xmore_data/      EGX data loading
xmore_news/      News ingestion pipelines
xmore_sentiment/ Sentiment analysis (Gemini, VADER, TextBlob)
models/          Trained ML models (.joblib)
migrations/      DB schema versioning
config/          Execution configuration
```

## Key Conventions

### Agent pattern
All agents inherit `BaseAgent` from `agents/agent_base.py` and return `AgentSignal` objects with: `agent_name`, `symbol`, `prediction` ("UP"/"DOWN"/"HOLD"), `confidence` (0–100), `reasoning` dict, `timestamp`.

### Database
- `database.py` provides `get_connection()` context manager for safe connections.
- Cross-DB: auto-converts SQLite `?` placeholders to PostgreSQL `%s`.
- Never use raw string interpolation for SQL — always parameterized queries.

### EGX market awareness
- EGX trades **Sun–Thu, 09:00–14:00 Cairo** (07:00–12:00 UTC).
- All cron schedules respect this window — no Friday/Saturday runs.
- Stock symbols use the `.CA` suffix (e.g., `COMI.CA`).

### Environment variables
`DATABASE_URL`, `NEWS_API_KEY`, `FINNHUB_API_KEY`, `GOOGLE_API_KEY`, `TELEGRAM_API_ID`, `TELEGRAM_API_HASH`. See `.env.example` for the full list.

### Config
`config.py` defines the EGX-30 stock list, market hours, API keys, and a 1.2× volatility adjustment factor.

## Pitfalls

- **Dual DB mode**: Code must work with both SQLite and PostgreSQL — test placeholder conversion when writing new queries.
- **yfinance rate limits**: Batch symbol lookups where possible; add retries on `HTTPError`.
- **Gemini API quotas**: `gemini_agent.py` and `sentiment_gemini.py` share the same `GOOGLE_API_KEY` quota.
- **Stale evaluations**: After schema changes, run `fix_stale_evaluations.py` to backfill missing fields.
