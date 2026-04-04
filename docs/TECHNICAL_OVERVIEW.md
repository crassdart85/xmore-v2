# Xmore Technical Overview

## 1. System Architecture

Xmore is a hybrid system with two main components:
-   **Python Backend**: A series of scheduled data collection and AI/ML processing jobs running on GitHub Actions.
-   **Node.js Frontend**: An Express.js web server and vanilla JavaScript frontend that serves pre-computed data to users.

This architecture is dictated by a key constraint: the production environment on Render.com is a Node.js environment and cannot execute Python code on demand. Therefore, all computationally intensive tasks are performed in a scheduled, pre-computation pipeline.

### 1.1 High-Level Flow
```
┌──────────────────────────────┐      ┌──────────────────────────────┐      ┌──────────────────────────┐
│        GitHub Actions        │      │      PostgreSQL Database     │      │      Node.js Web App       │
│      (Python Pipeline)       │      │         (on Render)          │      │ (Express API + JS Frontend)│
└───────────────┬──────────────┘      └───────────────┬──────────────┘      └───────────────┬──────────┘
                │                                     │                                     │
1. Collect data │                                     │                                     │
   (prices, news)                                     │                                     │
                ▼                                     │                                     │
┌──────────────────────────────┐                      │                                     │
│     AI & ML Processing       │                      │                                     │
│  - 5 AI Agents               │                      │                                     │
│  - Sentiment Analysis (Gemini)                      │                                     │
│  - Consensus & Scoring       │                      │                                     │
│  - Execution Realism Gate    │                      │                                     │
└───────────────┬──────────────┘                      │                                     │
                │                                     │                                     │
2. Write pre-computed results                         │                                     │
                └────────────────> 3. Store in DB     │                                     │
                                                      │                                     │
                                                      │ 4. Read pre-computed data           │
                                                      └──────────────────────────────────>  │
                                                                                            │
                                                                                            │
                                                                  5. Display data to user   │
                                                                                            │
```

### 1.2 Technology Stack
| Layer | Technology | Purpose |
|---|---|---|
| **Python Backend** | Python 3.10+ | Data collection, AI/ML agents, sentiment, simulation engines. |
| **Web Application** | Node.js, Express.js | API server and serving the frontend application. |
| **Frontend** | Vanilla JavaScript (ES6), CSS | Bilingual (EN/AR) responsive dashboard. No frameworks. |
| **Database** | PostgreSQL (Production), SQLite (Local Dev) | Primary data store for all pre-computed results. |
| **CI/CD & Compute** | GitHub Actions | Orchestration and execution of the entire Python pipeline. |
| **AI/ML** | Google Gemini, scikit-learn | Sentiment analysis, RAG, machine learning agents. |
| **Hosting** | Render.com | Hosts the Node.js application and PostgreSQL database. |

---

## 2. The Python Pre-computation Pipeline

The core logic of Xmore resides in a series of Python scripts orchestrated by GitHub Actions on a schedule. This pipeline is responsible for everything from data collection to signal generation and evaluation.

### 2.1 Key Pipeline Scripts

-   `collect_data.py`: Fetches daily price data (OHLCV) from `yfinance` and news headlines from various sources (NewsAPI, Finnhub).
-   `sentiment_gemini.py`: Uses the Google Gemini API to perform sentiment analysis on collected news headlines.
-   `run_agents.py`: The main inference engine. It runs the five distinct AI agents to generate signals.
-   `agents/`: Directory containing the individual agent implementations:
    -   `agent_ma.py`: Moving Average Crossover agent.
    -   `agent_rsi.py`: Relative Strength Index (RSI) momentum agent.
    -   `agent_volume.py`: Volume spike and anomaly detection agent.
    -   `agent_ml.py`: A machine learning agent (e.g., Random Forest).
    -   `gemini_agent.py`: An agent that uses Gemini for predictive signals.
-   `consensus_engine.py`: Aggregates the outputs from all agents into a single daily consensus signal (BUY/HOLD/SELL) and a proprietary Xmore Score.
-   `engines/agent_weights.py`: Computes softmax-based dynamic agent weights from recent directional accuracy, with temperature scaling and minimum floor (5%). Logs weight history to `agent_weights_log` for auditing.
-   `engines/execution_agent.py`: Applies a critical "execution realism" filter to signals, accounting for transaction costs, slippage, and market regime.
-   `engines/scoring_formatter.py`: Computes a universal investor score and translates it into six different formats (e.g., letter grade, stars).
-   `engines/event_detector.py`: Scans recent news for high-impact events (CBE rate decisions, earnings, regulatory actions, index rebalances, price gaps) and triggers targeted sentiment refreshes before the agent pipeline runs.
-   `engines/job_locks.py`: Advisory TTL-based locking to prevent race conditions between concurrent pipeline steps (e.g. `intraday-price-update` and `catchup-evaluation`).
-   `evaluate.py`: Evaluates predictions with multi-metric scoring: directional accuracy, magnitude-weighted score, Brier calibration score, signal strength, and actual return. Supports `--force` flag to bypass lock checks.
-   `evaluate_performance.py`: A daily job that evaluates the accuracy and financial performance (alpha) of past predictions at D+1 and D+5 horizons. Includes Information Coefficient (IC) computation via Spearman rank correlation.

### 2.2 CI/CD Automation (GitHub Actions)
The system is fully automated with multiple scheduled jobs, including:
-   **Intraday Updates**: Price and news updates during EGX trading hours.
-   **Post-Market Pipeline**: A major job that runs after the market closes to generate the next day's signals.
-   **Daily & Weekly Jobs**: Includes full pipeline runs, backtesting, and evaluation catch-ups.

---

## 3. Advanced Simulation Engines

Xmore includes sophisticated simulation engines for forecasting and risk analysis.

### 3.1 GARCH & Regime Engine
-   **`engines/garch_engine.py`**: Implements GARCH, GJR-GARCH, and EGARCH models to analyze and forecast volatility for individual assets. It uses AIC for model selection.
-   **`engines/regime_model.py`**: Detects market regimes using HMM (primary, if hmmlearn installed and >=252 observations) or MA/volatility deterministic fallback. The `get_current_regime()` function returns regime label (bull/bear/high_vol), probability, stability, and drift/vol metrics. Regime feedback is injected into agent signals via `REGIME_SIGNAL_MODIFIERS` in `run_agents.py`.
-   **`engines/simulation_core.py`**: A unified `SimulationEngine` that combines the GARCH and regime outputs to run multivariate Monte Carlo simulations. Supports `macro_context` in `SimulationConfig` for macro-adjusted drift and volatility (risk score dampens drift by up to 30%, high interest rate environments add +15% vol).
-   **`engines/macro_data.py`**: `MacroDataProvider` class that caches Egypt macro indicators (CBE rate, USD/EGP, CPI YoY, GDP growth) in the `macro_indicators` DB table. Computes a composite `macro_risk_score` (0–1) fed into `SimulationConfig` for regime-aware simulations.

---

## 4. AI Research Assistant & RAG

Xmore features an AI-powered market assistant integrated into the web dashboard, built using Retrieval-Augmented Generation (RAG).

-   **`rag/embedder.py`**: A service to process and embed external documents (like ETF factsheets) into vector representations using Gemini's `text-embedding-004` model.
-   **`rag/retriever.py`**: Performs semantic search over the embedded documents to find relevant context for user queries.
-   **`web-ui/routes/rag.js`**: The Node.js API endpoint for the chat assistant. It enriches user prompts with a significant amount of real-time market context, including:
    -   Static EGX market knowledge (trading hours, rules, indices).
    -   A live-queried list of all ~190 tracked stocks.
    -   Current signals, prices, and sentiment data.
    -   The user's personal portfolio data.
-   **`web-ui/services/openbbMcpBridge.js`**: An MCP bridge that enriches the RAG chat with live market data. Extracts EGX symbols from user queries, fetches live quotes from OpenBB API (if running) and macro context from the local DB cache. When enrichment succeeds, a "Live data" badge is shown next to the assistant's response in the chat widget.
-   This enriched context allows the Gemini model to provide highly relevant and accurate answers about the Egyptian market.

---

## 5. Database Architecture

The system uses a dual-database strategy to facilitate both local development and production deployment.

-   **Production**: A managed PostgreSQL instance on Render.com.
-   **Local Development**: A simple `xmore_event_intel.db` SQLite file.

A custom database abstraction layer in `database.py` allows the same Python code to run seamlessly against both database types. The Node.js server (`web-ui/server.js`) also contains a similar abstraction to switch between `pg` and `sqlite3` npm packages based on the `DATABASE_URL` environment variable. This ensures that developers can work offline without needing a full PostgreSQL server.

---

## 6. OpenBB EGX Data Provider

Xmore includes a standalone OpenBB-compatible data provider package (`openbb_egx/`) for Egyptian Exchange market data:

-   **`openbb_egx/models/equity_historical.py`**: Historical OHLCV data via TradingView Scanner API (primary) with yfinance fallback. Pydantic v2 query/data models.
-   **`openbb_egx/models/equity_quote.py`**: Live quote fetcher for EGX symbols.
-   **`openbb_egx/models/equity_search.py`**: Symbol search across EGX-listed equities.
-   **`openbb_egx/models/market_snapshot.py`**: Full market snapshot (all active EGX symbols).
-   **14 unit tests** in `openbb_egx/tests/test_egx_provider.py`.

---

## 7. Pipeline Coordination

### 7.1 Advisory Job Locks

`engines/job_locks.py` provides TTL-based advisory locks to prevent concurrent pipeline steps from reading incomplete data. For example, `catchup-evaluation` checks if `intraday-price-update` holds a lock before proceeding.

- `acquire_lock(job_name, ttl_seconds)` / `release_lock(job_name)` / `is_lock_held(job_name)`
- Fail-open design: if the lock system itself fails, the pipeline continues.
- `job_locks` table with `expires_at` for automatic stale lock cleanup.

### 7.2 Schedule Stagger

The `catchup-evaluation` cron at 12:00 UTC is staggered to 12:15 UTC to avoid overlapping with `intraday-price-update` (which runs at 12:00).

---

*Last Updated: April 4, 2026*
