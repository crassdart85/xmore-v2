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
-   `engines/execution_agent.py`: Applies a critical "execution realism" filter to signals, accounting for transaction costs, slippage, and market regime.
-   `engines/scoring_formatter.py`: Computes a universal investor score and translates it into six different formats (e.g., letter grade, stars).
-   `evaluate_performance.py`: A daily job that evaluates the accuracy and financial performance (alpha) of past predictions at D+1 and D+5 horizons.

### 2.2 CI/CD Automation (GitHub Actions)
The system is fully automated with multiple scheduled jobs, including:
-   **Intraday Updates**: Price and news updates during EGX trading hours.
-   **Post-Market Pipeline**: A major job that runs after the market closes to generate the next day's signals.
-   **Daily & Weekly Jobs**: Includes full pipeline runs, backtesting, and evaluation catch-ups.

---

## 3. Advanced Simulation Engines

Xmore includes sophisticated simulation engines for forecasting and risk analysis.

### 3.1 GARCH & HMM Engine
-   **`engines/garch_engine.py`**: Implements GARCH, GJR-GARCH, and EGARCH models to analyze and forecast volatility for individual assets. It uses AIC for model selection.
-   **`engines/regime_model.py`**: Implements a Gaussian Hidden Markov Model (HMM) to detect underlying market regimes (e.g., Bull, Bear). It uses BIC for model selection and can simulate future regime paths.
-   **`engines/simulation_core.py`**: A unified `SimulationEngine` that combines the GARCH and HMM outputs to run multivariate Monte Carlo simulations, providing a forward-looking view of potential market behavior.

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
-   This enriched context allows the Gemini model to provide highly relevant and accurate answers about the Egyptian market.

---

## 5. Database Architecture

The system uses a dual-database strategy to facilitate both local development and production deployment.

-   **Production**: A managed PostgreSQL instance on Render.com.
-   **Local Development**: A simple `xmore_event_intel.db` SQLite file.

A custom database abstraction layer in `database.py` allows the same Python code to run seamlessly against both database types. The Node.js server (`web-ui/server.js`) also contains a similar abstraction to switch between `pg` and `sqlite3` npm packages based on the `DATABASE_URL` environment variable. This ensures that developers can work offline without needing a full PostgreSQL server.
