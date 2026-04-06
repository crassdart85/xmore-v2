# Xmore KSA Trading System

An automated trading and market-intelligence system tailored for the Saudi Exchange (Tadawul). This branch targets the KSA deployment, with a Node dashboard, Python data pipelines, and KSA-specific routing and APIs.

## Project Overview

Xmore KSA is built to:

1. Collect Tadawul prices, news, and market context.
2. Run multiple agents and KSA-specific consensus logic.
3. Generate daily directional signals for `.SR` symbols.
4. Evaluate realized outcomes and alpha versus TASI.
5. Serve KSA dashboard, briefing, pro, and track-record views.

## KSA Deployment Notes

The KSA production app depends on two systems:

- Render web service
  - serves `web-ui/server.js`
  - runs the KSA schema initializer `web-ui/init-db-ksa.js`
- GitHub Actions pipeline
  - runs `.github/workflows/ksa-daily-pipeline.yml`
  - populates prices, signals, regime, evaluations, and other KSA data

If the GitHub Actions pipeline is not writing fresh KSA rows, the site will render with empty states even when the frontend is correct.

## Current Status

Recent fixes on branch `xmore-ksa` include:

- KSA route/page wiring for `/track-record`
- KSA dashboard endpoints:
  - `/api/ksa/freshness`
  - `/api/ksa/ticker`
- KSA scoping on shared briefing, performance, and ETF routes
- schema-compatibility hardening for:
  - `trade_recommendations`
  - `consensus_results`
  - `regime_log`
  - `prices`

Remaining deployment risk is operational:

- Render must deploy from branch `xmore-ksa`
- GitHub Actions must successfully populate the production database

## Installation

### Prerequisites

- Python 3.8+
- Node.js 18+
- PostgreSQL in production, SQLite locally
- required API keys for the KSA workflow

### Setup

1. Clone the repository:

```bash
git clone <repository_url>
cd Xmore-ksa
```

2. Install Python dependencies:

```bash
pip install -r requirements.txt
```

3. Install web dependencies:

```bash
cd web-ui
npm install
cd ..
```

4. Configure environment variables:

- `DATABASE_URL`
- `MARKET=KSA`
- provider/API keys used by the KSA workflow

5. Initialize the KSA database schema:

```bash
node web-ui/init-db-ksa.js
```

## Usage

### Web app

```bash
node web-ui/server.js
```

### KSA signal pipeline

```bash
python run_agents_ksa.py
```

### Evaluation

```bash
python evaluate.py
python -m engines.evaluate_performance
```

### KSA data collection

```bash
python collect_data.py --prices-only
python collect_data.py --news-only
```

## Verification

After a KSA deploy, verify:

```bash
curl https://xmore-ksa.onrender.com/api/ksa/freshness
curl https://xmore-ksa.onrender.com/api/ksa/ticker
curl https://xmore-ksa.onrender.com/api/ksa/signals/today
curl https://xmore-ksa.onrender.com/api/ksa/track-record/summary
```

Expected:

- no `.CA` symbols on the KSA domain
- no `404` from KSA dashboard APIs
- KSA pages render even if data is temporarily stale
- metrics populate once the GitHub Actions pipeline writes fresh KSA rows

## Tadawul Data Limitations

- some Tadawul stocks have low daily volume, which can amplify slippage
- Tadawul trades Sunday through Thursday
- free `.SR` providers can be delayed or incomplete
- empty UI sections usually indicate missing pipeline output, not only frontend defects

## Architecture

- Web app: `web-ui/`
- Pipelines: repo root scripts and `engines/`
- Database: shared PostgreSQL in production, SQLite locally
- Frontend: KSA HTML/JS pages under `web-ui/public/`

## Disclaimer

This software is for informational and research purposes only. Do not use it for real-money trading without independent validation, fresh data verification, and proper risk controls.
