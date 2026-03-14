# Xmore — Business Presentation

---

## Slide 1 — Title

# Xmore
### AI-Powered Stock Intelligence for the Egyptian Exchange

> Five AI agents. One consensus. Pre-market every day.

**Live at:** xmore-project.onrender.com
**Market:** Egyptian Exchange (EGX) — ~190 stocks
**Status:** Production · March 2026

---

## Slide 2 — The Problem

### Egyptian retail investors trade blind

- **No pre-market intelligence** — brokers provide prices, not signals
- **Information asymmetry** — institutional desks run quantitative models; retail traders rely on rumour and WhatsApp groups
- **EGX-specific friction is ignored** — round-trip costs ≈ 0.70%, ±10% daily limit, thin liquidity in small caps frequently cause slippage that erodes gains
- **No accountability** — signal providers in Egypt have no public track record; past calls vanish
- **Language barrier** — all global quant tools are English-only; Arabic-speaking traders are underserved
- **Benchmark manipulation** — performance ratios calculated with US 5% risk-free rate instead of Egypt CBE 27.25% — inflates Sharpe by 3–4×

---

## Slide 3 — The Solution

### Xmore: a daily AI consensus engine built for EGX

```
5 AI Agents → Consensus Engine → Execution Gate → 6-Mode Scoring → Dashboard
```

Each trading day before 09:00 Cairo:
1. Five agents independently analyse every tracked EGX stock
2. A weighted consensus BUY / HOLD / SELL is produced with an Xmore Score (0–100)
3. BUY signals are filtered through real friction (costs, liquidity, regime)
4. A composite investor score is translated into 6 output formats simultaneously
5. Results are published in a bilingual (EN/AR) dashboard and API

**No login required** to view signals — full transparency by design.

---

## Slide 4 — The 5 AI Agents

| Agent | Method | Weight |
|---|---|---|
| **MA Crossover** | 20/50-day moving average crossover with volume confirmation | Equal |
| **RSI Agent** | Relative Strength Index oversold/overbought + divergence | Equal |
| **Volume Spike** | Abnormal volume detection relative to 20-day ADV | Equal |
| **Random Forest ML** | Trained on OHLCV + technical features, walk-forward validated | Equal |
| **Gemini LLM** | Google Gemini 2.5 Flash with live news sentiment + market context | 0.20 |

Agents vote independently. The **Xmore Score** (0–100) aggregates bull pressure across all votes:

> `bull×0.30 + (100−bear)×0.25 + agreement_ratio×0.25 + avg_confidence×0.20`

---

## Slide 5 — Execution Realism (Unique Differentiator)

### We model what it actually costs to trade EGX

Most signal providers show raw alpha. Xmore shows **tradeable** alpha.

**Every BUY signal is gated by:**

| Check | Detail |
|---|---|
| Round-trip cost | Brokerage + stamp + FRA + EGX + Misr clearing ≈ 0.70% |
| Minimum edge | Signal must offer ≥ 3× round-trip cost to be approved |
| Liquidity slippage | High ADV: 10 bps · Mid: 25 bps · Low: 60 bps |
| Market regime | EGX30 vs MA20 — new longs blocked in BEAR regime |
| Gap risk | Stops floored at ±10% EGX daily limit |
| Trailing stop | Activates day 20 at 6% below peak; hard exit day 45 |

Blocked signals are logged with reason — full audit trail.

**All execution checks run during the pre-market pipeline — results are waiting when markets open.**

---

## Slide 6 — Institutional-Grade Performance Metrics

### We measure ourselves against international standards — EGX-calibrated

All ratios use **Egypt CBE rate (27.25%)** not US 5%, and **247 EGX trading days** not 252.

| Metric | What it shows |
|---|---|
| **Sharpe Ratio** | Risk-adjusted return above CBE deposit rate |
| **Sortino Ratio** | Penalises only downside volatility |
| **Calmar Ratio** | Annualised return ÷ max drawdown |
| **Information Ratio** | Alpha consistency vs EGX30 benchmark |
| **Max Drawdown** | Peak-to-trough with recovery date |
| **Rolling 30-day Sharpe** | Momentum of risk-adjusted performance |
| **Beta vs EGX30** | Market sensitivity |
| **Up/Down Capture** | How much of bull/bear moves Xmore participates in |

A public **Track Record** page (`/track-record`) shows all metrics — no login required.

---

## Slide 7 — Universal Investor Scoring (6 Formats)

### The same signal, in whatever language your audience speaks

```
Composite Score = Consensus×0.40 + Execution×0.25 + Regime×0.20 + Momentum×0.15
```

**All six formats are computed simultaneously — one score, six views:**

| Mode | Example output | Actionable threshold |
|---|---|---|
| Xmore Native | 0.84 | ≥ 0.62 |
| Score (0–100) | 84 | ≥ 62 |
| Letter Grade | A | ≥ B |
| Stars | ★★★★☆ (4.0) | ≥ 3.5 |
| Signal Tier | A | ≥ B |
| Conviction | HIGH | ≥ MEDIUM |

All 6 are available simultaneously via API (`GET /api/signals/scored/compare`).
Dashboard mode selector lets users toggle format without a page reload.

---

## Slide 8 — Product Suite

### One platform, multiple surfaces

| Surface | URL | Audience |
|---|---|---|
| **Main Dashboard** | `/` | Retail traders — daily signals, screener, portfolio |
| **Session Sheet** | `/session` | Active traders — pivots, ATR, patterns, live P&L simulator |
| **Xmore Pro** | `/pro` | Professional terminal — live market overview, macro brief |
| **Track Record** | `/track-record` | Investors — verified performance, equity curve, risk metrics |
| **Docs** | `/docs` | Onboarding — full bilingual feature documentation |
| **Admin** | `/admin` | Operator — RAG documents, pipeline health, ETF management |

All surfaces: **bilingual EN/AR with full RTL layout**.

---

## Slide 9 — Track Record

### Transparent, audited, bilingual

- **Live predictions** since 11 January 2026 — evaluated at D+1 and D+5 by comparing predicted direction to actual close
- **60-day historical simulation** — same agent logic applied to past EGX prices, clearly tagged **SIM**
- **Walk-forward backtest** — re-runs every Sunday on all ~190 EGX stocks

**Live production numbers (verified on Render, March 2026):**

| Metric | Value | Notes |
|---|---|---|
| Signals evaluated | **277** | Live since Jan 11, 2026 |
| Win rate (D+1) | **46.9%** | Predicted direction = actual direction |
| Avg return per signal | **+0.27%** | D+1, including losers |
| Win/Loss ratio | **1.44×** | Winners avg 44% larger than losers |
| Profit factor | **1.34** | Gross profit ÷ gross loss |
| Expectancy per trade | **+0.23%** | Expected return on any signal |
| Sharpe Ratio | **1.70** | EGX-calibrated (CBE 27.25%, 247 days) |
| Sortino Ratio | **3.43** | Downside-only volatility penalised |
| Information Ratio | **1.71** | Alpha consistency vs EGX30 |
| Max consecutive wins | **10** | Longest winning streak |
| Max consecutive losses | **9** | Longest losing streak |

**Track Record page features:**
- Equity curve: cumulative Xmore return vs EGX30 benchmark (Chart.js)
- Rolling 30/60/90-day KPI windows
- Per-agent methodology cards
- Walk-forward backtest results table (sorted by directional accuracy)
- Top stocks by alpha generated
- Paginated prediction log with CSV export
- Risk metrics: Sharpe, Sortino, Calmar, beta, drawdown details

Public URL — share directly with prospective investors: `/track-record`

---

## Slide 10 — ETF & Macro Intelligence

### Beyond single stocks

**EGX ETF Dashboard**
- 13 locally-listed Egyptian ETFs sourced from Mubasher (Arabic scraper)
- 4 global Egypt-focused ETFs (EGPT, EEMX, FM, FRDM) via yfinance
- NAV, premium/discount, holdings modal, PDF factsheet RAG search
- Commodity ETPs correctly classified (not mislabelled as equity ETFs)

**FX & Gold Rates**
- Live USD/EGP, USD/SAR, SAR/EGP, XAU/USD
- Gold prices: 24K, 21K, 18K per gram EGP + Gold Pound EGP
- 90-day sparkline history — auto-accumulates on every page load

**Macro Brief (Xmore Pro)**
- Gemini 2.5 Flash with Google Search grounding
- Real-time EGX30 level, USD/EGP, inflation, interest rate, key movers
- Clickable web source citations — refreshes hourly

---

## Slide 11 — Market Assistant (RAG + Chat)

### Ask anything. Get EGX-aware answers.

**Context injected automatically:**
- Today's consensus signals and Xmore Scores
- Live prices, volume leaders, sector performance
- Latest news sentiment (Gemini-analysed Arabic + English headlines)
- Your forecast portfolio positions (when signed in)
- ETF factsheets (PDF RAG via Gemini embeddings)

**Quick chips:** "Macro Brief" · "Top Movers" · "Buy Signals"

Arabic-aware: keyword extraction works in both languages.

---

## Slide 12 — Technology Stack

### Production-ready, cloud-native, zero-maintenance

```
GitHub Actions (cron, 9 jobs)
        │
        ├─ Python: 5 agents + consensus + execution gate + scoring + metrics
        │          (ALL Python runs here — never on Render)
        ↓
PostgreSQL (Render.com)
        │  All pre-computed values stored here
        ↓
Node.js/Express API (Render.com)
        │  Reads pre-computed rows — zero Python at request time
        ↓
Vanilla JS Dashboard (bilingual, dark/light, responsive)
```

| Layer | Technology |
|---|---|
| Agent engine | Python — pandas, scikit-learn, yfinance, Gemini SDK |
| API server | Node.js + Express |
| Database | SQLite (local) / PostgreSQL (production) |
| AI | Google Gemini 2.5 Flash (signals + chat + RAG + macro) |
| CI/CD | GitHub Actions — 9 scheduled jobs |
| Hosting | Render.com — auto-deploy on push |
| Auth | JWT in HTTP-only cookie |

**Key architectural decision:** Python runs exclusively in CI. Node.js reads pre-computed results from PostgreSQL. This guarantees API response times < 500 ms regardless of model complexity.

---

## Slide 13 — Competitive Positioning

| Feature | Xmore | Generic screeners | Broker platforms |
|---|---|---|---|
| EGX-specific signals | ✓ | Partial | ✗ |
| 5-agent consensus | ✓ | ✗ | ✗ |
| Friction-adjusted signals | ✓ | ✗ | ✗ |
| Public audited track record | ✓ | ✗ | ✗ |
| Arabic RTL interface | ✓ | Rare | Partial |
| EGX-correct risk metrics (CBE RF) | ✓ | ✗ | ✗ |
| 6-mode investor scoring | ✓ | ✗ | ✗ |
| ETF + macro intelligence | ✓ | Partial | ✗ |
| RAG document search | ✓ | ✗ | ✗ |
| Walk-forward backtest (weekly) | ✓ | ✗ | ✗ |
| Free tier | ✓ | Varies | ✗ |

---

## Slide 14 — Architecture Strength: Why Pre-computation Wins

### The Python-on-Render constraint is by design, not by accident

**The problem:** Render `env: node` cannot run Python. All statistical computation (Sharpe, regime filter, composite scoring) must be done elsewhere.

**The response:** Every metric is pre-computed during scheduled GitHub Actions jobs and stored as a column value in PostgreSQL. The Node.js API is a thin read layer.

**Why this is actually better:**

| Naive approach | Xmore approach |
|---|---|
| Compute metrics on user request (Python process) | Pre-compute in CI, store result |
| 10–30s response time for complex metrics | < 50 ms read from indexed column |
| Cold-start failures if Python unavailable | DB always has the last known value |
| Cannot serve 500 concurrent users | Scales horizontally with connection pool |

**Real-time exceptions:** Gemini chat (Node.js ↔ Gemini API directly), FX rates (Node.js ↔ open.er-api.com directly), virtual P&L (pure arithmetic in Node.js).

---

## Slide 15 — Roadmap

### Near-term
- [ ] Real-time intraday signal updates (SSE from Node.js)
- [ ] Push notifications (email / Telegram) when signal changes
- [ ] Render Background Worker for on-demand Python — enables real-time regime re-check
- [ ] Brokerage API integration (direct order placement)

### Medium-term
- [ ] Paid Pro tier with advanced screener and API access keys
- [ ] Portfolio optimiser (mean-variance, EGX constraints)
- [ ] Mobile app (React Native, same API)
- [ ] Expansion to ADX (Abu Dhabi) and Tadawul (Saudi Arabia)

---

## Slide 16 — Summary

### Why Xmore

1. **Only** pre-market AI consensus engine built specifically for EGX
2. **Friction-realistic** — models actual Egyptian trading costs before recommending
3. **Fully bilingual** — Arabic-first in a market where Arabic dominates
4. **Institutionally measured** — EGX-correct risk metrics (CBE 27.25%), public track record
5. **6-mode scoring** — the same signal expressed in any format an investor prefers
6. **Open by design** — predictions and performance are public; trust is earned, not claimed
7. **Production-running** — live since Jan 11, 2026; 277+ signals evaluated; automated pipeline, zero manual intervention
8. **Fast by architecture** — pre-computed results mean the API always responds in < 500 ms

> **Xmore turns Egypt's information asymmetry into a solvable engineering problem.**

---

*xmore-project.onrender.com · GitHub: crassdart85/xmore-v2*
