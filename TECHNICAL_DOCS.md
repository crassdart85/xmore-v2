# 📈 Xmore Stock Prediction System - Technical Documentation

## Overview

Xmore is an advanced stock market prediction system that leverages **Ensemble Machine Learning** to forecast stock price movements. Unlike traditional systems that rely solely on technical indicators or simple heuristics, Xmore integrates:

1.  **Quantitative Data**: Historical OHLCV (Open, High, Low, Close, Volume) data.
2.  **Qualitative Data**: **Financial News Sentiment Analysis** using **FinBERT** (a BERT model fine-tuned on financial text).
3.  **Technical Analysis**: Advanced indicators (RSI, MACD, Bollinger Bands) generated effectively inside the feature engineering pipeline.

The system targets a **7-day prediction horizon**, classifying trends as **UP** (Buy), **DOWN** (Sell), or **FLAT** (Hold).

---

## 🏗 System Architecture

The project consists of three main layers:

### 1. Data Layer (SQLite)
*   **`prices` table**: Stores historical stock data sourced from Yahoo Finance.
*   **`news` table**: Stores financial news headlines and their encoded sentiment scores (FinBERT).
*   **`predictions` / `evaluations` tables**: Store agent outputs and performance metrics.

### 2. Logic & ML Layer (Python)
*   **`collect_data.py`**: ETL script. Fetches prices (yfinance) and News (NewsAPI), runs FinBERT inference, and stores data.
*   **`features.py`**: Centralized feature engineering module. Calculates RSI, MACD, Bollinger Bands, and merges sentiment data.
*   **`train_model.py`**: Trains a **Random Forest Classifier** using **TimeSeriesSplit** validation to prevent look-ahead bias. Saves model to `models/stock_predictor.pkl`.
*   **`run_agents.py`**: The inference engine. Loads the latest data, applies the Random Forest model, and generates predictions.
*   **`evaluate.py`**: Back-testing and self-correction module. Compares past predictions with actual outcomes to track accuracy.

### 3. Presentation Layer (Node.js/Express)
*   **`web-ui/`**: A lightweight dashboard to visualize active predictions, confidence scores, and historical accuracy.

---

## 🚀 Execution Pipeline

The entire workflow is orchestrated by `run_pipeline.py`.

### Step-by-Step Flow:

1.  **Data Collection**:
    ```bash
    python collect_data.py
    ```
    *   *Input*: Yahoo Finance API, NewsAPI.
    *   *Process*: Downloads missing price data; fetches recent news; uses `ProsusAI/finbert` to generate sentiment scores (-1 to 1).
    *   *Output*: DB updates.

2.  **Model Training**:
    ```bash
    python train_model.py
    ```
    *   *Process*: Loads all history; generates features; creates ternary labels (UP/DOWN/FLAT); trains Random Forest; validates via 5-fold Time Series split.
    *   *Output*: `models/stock_predictor.pkl`

3.  **Inference**:
    ```bash
    python run_agents.py
    ```
    *   *Process*: Loads `MLAgent`; loads latest prices/news; generates features on-the-fly; predicts next 7 days.
    *   *Output*: DB `predictions` table.

4.  **Evaluation**:
    ```bash
    python evaluate.py
    ```
    *   *Process*: Checks simple accuracy of expired predictions.
    *   *Output*: DB `evaluations` table.

5.  **Visualization**:
    ```bash
    # In /web-ui directory
    npm start
    ```
    *   *Output*: Dashboard at `http://localhost:3000`.

---

## 📂 Key Files Description

| File | Description |
| :--- | :--- |
| `run_pipeline.py` | **Master script** to run the full end-to-end process. |
| `agents/agent_ml.py` | Wrapper class for the ML model; handles loading and inference. |
| `features.py` | Shared library for calculating technical indicators & sentiment features. |
| `config.py` | Configuration constants (API keys, stock list, thresholds). |
| `web-ui/server.js` | Express server providing API endpoints for the dashboard. |

---

## 🛠 Dependencies & Setup

### Python Requirements
*   `pandas`, `numpy`: Data manipulation.
*   `scikit-learn`: Machine Learning (Random Forest).
*   `yfinance`: Stock data API.
*   `newsapi-python`: News aggregation.
*   `transformers`, `torch`: FinBERT Sentiment Analysis.

### Installation
1.  **Install Python Deps**:
    ```bash
    pip install pandas numpy scikit-learn yfinance newsapi-python transformers torch
    ```
2.  **Install Node Deps** (for Dashboard):
    ```bash
    cd web-ui
    npm install
    ```
3.  **Run**:
    ```bash
    python run_pipeline.py
    ```

---

## 🤖 Model Details

*   **Algorithm**: Random Forest Classifier (Ensemble).
*   **Features**:
    *   **Trend**: SMA_10, SMA_50, MACD, Signal Line.
    *   **Momentum**: RSI (14-day).
    *   **Volatility**: Bollinger Upper/Lower, 20-day Volatility.
    *   **Sentiment**: Daily average FinBERT score.
*   **Validation**: TimeSeriesSplit (5 Folds). ensures the model is not tested on data from the past relative to the training set.
*   **Metric**: Accuracy (Binary/Ternary Classification).

---

## 🔮 Future Improvements

1.  **Deep Learning**: Implement LSTM or Transformer-based time-series models for potentially better sequence modeling.
2.  **Hyperparameter Tuning**: Use GridSearch to optimize Random Forest parameters.
3.  **More Data Sources**: Integrate macro-economic indicators (fed rates, inflation) or alternative data (social media).
4.  **Automated Trading**: Connect to a brokerage API (e.g., Alpaca) for paper trading.

---

## 📋 Recent Updates (March 2026)

### Signal Quality Recalibration and Live Validation (March 21, 2026)
- Recomputed `calibrated_confidence`, `expected_edge_pct`, and `ranking_score` after the later momentum-alignment penalty in [run_agents.py](f:/xmore-project/run_agents.py) so downstream ranking reflects the final adjusted signal state instead of pre-penalty values.
- Extended recommendation payloads in [engines/trade_recommender.py](f:/xmore-project/engines/trade_recommender.py) to carry `raw_confidence`, `calibrated_confidence`, `expected_edge_pct`, `ranking_score`, and `momentum_alignment` into the scored-signals layer.
- Updated [engines/scoring_formatter.py](f:/xmore-project/engines/scoring_formatter.py) so scored signals prefer calibrated confidence for consensus quality, expected edge for execution quality, and momentum alignment for momentum quality, while keeping legacy fallbacks for older rows.
- Added production smoke coverage in [web-ui/scripts/live-smoke.js](f:/xmore-project/web-ui/scripts/live-smoke.js) and npm scripts in [web-ui/package.json](f:/xmore-project/web-ui/package.json):
    - `npm run smoke:prod`
    - `npm run smoke:url -- https://your-base-url`
- Validation status:
    - Targeted tests passed: `pytest tests/test_scoring_formatter.py`
    - Deployed API smoke passed against Render on March 21, 2026.
    - Live recommendation generation executed successfully against production PostgreSQL after installing missing local runtime dependencies (`finnhub-python`, `google-genai`, `python-dotenv`).
    - The March 21 production run persisted no new `trade_recommendations` or `scored_signals` rows because the run occurred with the target market closed, and [generate_daily_trade_recommendations](run_agents.py#L1939) skips per-symbol processing when the target market is closed.

### DCF Valuation Engine (New Feature)
- **Added**: Standalone Discounted Cash Flow (DCF) valuation module (`agents/dcf/`)
- **Frequency**: Runs once per week (Sundays) via `run_agents.py`
- **Inputs**: Historical financial statements, market data, KSA-calibrated WACC
- **Outputs**: Fair value estimates (bull/base/bear scenarios + composite), stored in `dcf_valuations` table
- **Integration**: DCF signals feed into the multi-agent consensus engine, boosting weight on deep value or punishing on overvaluation
- **Modules**: dcf_config, data_collector, fcf_projector, wacc_calculator, dcf_engine, scenario_runner, dcf_store, run_dcf, dcf_agent

### Bug Fixes & Code Quality Improvements
1. **Database Schema Fix**: Removed invalid `DATE()` expressions from UNIQUE constraints (SQLite/PostgreSQL incompatibility)
2. **Weighted Average Normalization**: Fixed scenario_runner to renormalize composite weights when scenarios fail to compute
3. **Config Parameter Missing**: Added missing `config` parameter in fcf_projector bank FCF projection
4. **Redundant Logic**: Removed pointless if-else in upside_pct calculation
5. **SQLite Row Conversion**: Fixed Row object to dict conversion using `dict(zip(...))`  
6. **Code Quality**: Fixed naming convention (DCf_TABLE_SQL → DCF_TABLE_SQL), removed unreachable return statements
7. **Track Record API**: Updated `web-ui/routes/track-record.js` to calculate accurate "Last Updated" timestamp using multiple table sources

### Mobile CSS Optimizations (March 2026)
**Comprehensive responsive design improvements for mobile devices (640px and below):**

- **Header/Navigation**: Completely restructured layout to prevent overlapping; secondary nav links now hidden on mobile; buttons properly stack with adequate spacing
- **Spacing & Sizing**: 
  - Header padding reduced to 8-10px for mobile
  - Button heights: 36px minimum (touch-friendly)
  - Gap spacing: 6-8px for compact mobile layout
- **Stats Grid & Cards**: Changed from 4-column to 2-column on mobile; proper padding (10-12px) per card
- **Navigation Tabs**: Horizontal scroll enabled with `-webkit-overflow-scrolling: touch`; better spacing (4px gaps); font size 0.75em for compact display
- **Tables & Data**: 
  - Proper min-widths (380-560px) enable horizontal scroll without breaking layout
  - Reduced padding (8px) per cell
  - Sticky headers with proper z-index
- **Text Handling**: Added `word-break: break-word` + `overflow-wrap: break-word` to all text elements; proper line-height (1.2-1.4) for readability
- **Modals & Overlays**: Sized properly for mobile (96vw, 90vh max); no content overflow
- **Files Updated**: 
  - `web-ui/public/style.css` — Added 350+ lines of comprehensive mobile CSS
  - `web-ui/public/track-record.css` — Enhanced track-record page mobile styling
  - `web-ui/public/base.css` — Improved header/topbar mobile layout
  - `web-ui/public/performance-dashboard.css` — Better performance metrics on mobile

**Result**: No more overlapping elements, consistent spacing, readable font sizes, and touch-friendly interface across all pages and viewports.
