# Xmore — Business Presentation

---

## Slide 1 — Title

# Xmore
### AI-Powered Stock Intelligence for the Egyptian Exchange

> Five AI agents. One consensus. Pre-market every day.

**Live at:** xmore-project.onrender.com
**Market:** Egyptian Exchange (EGX) — ~190 stocks

---

## Slide 2 — The Problem

### Egyptian retail investors trade blind

- **No pre-market intelligence** — brokers provide prices, not signals
- **Information asymmetry** — institutional desks run quantitative models; retail traders rely on rumour and WhatsApp groups
- **EGX-specific friction is ignored** — round-trip costs ≈ 0.70%, ±10% daily limit, thin liquidity in small caps frequently cause slippage that erodes gains
- **No accountability** — signal providers in Egypt have no public track record; past calls vanish
- **Language barrier** — all global quant tools are English-only; Arabic-speaking traders are underserved

---

## Slide 3 — The Solution

### Xmore: a daily AI consensus engine built for EGX

```
5 AI Agents → Consensus Engine → Execution Gate → Dashboard
```

Each trading day before 09:00 Cairo:
1. Agents analyse every tracked EGX stock
2. A weighted consensus BUY / HOLD / SELL is produced
3. Signals are filtered through real friction (costs, liquidity, regime)
4. Results are published in a bilingual (EN/AR) dashboard and API

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

A public **Track Record** page (`/track-record`) shows all metrics — no login required.

---

## Slide 7 — Product Suite

### One platform, multiple surfaces

| Surface | URL | Audience |
|---|---|---|
| **Main Dashboard** | `/` | Retail traders — daily signals, screener, portfolio |
| **Session Sheet** | `/session` | Active traders — pivots, ATR, patterns, live P&L simulator |
| **Xmore Pro** | `/pro` | Professional terminal — live market overview, macro brief |
| **Track Record** | `/track-record` | Investors — verified performance, equity curve, risk metrics |
| **Docs** | `/docs` | Onboarding — full bilingual feature documentation |

All surfaces: **bilingual EN/AR with full RTL layout**.

---

## Slide 8 — Investor Scoring (6 Formats)

### The same signal, in whatever language your audience speaks

```
Composite Score = Consensus×0.40 + Execution×0.25 + Regime×0.20 + Momentum×0.15
```

| Mode | Example output | Threshold |
|---|---|---|
| Xmore Native | 0.84 | ≥ 0.62 |
| Score (0–100) | 84 | ≥ 62 |
| Letter Grade | A | ≥ B |
| Stars | ★★★★☆ (4.0) | ≥ 3.5 |
| Signal Tier | A | ≥ B |
| Conviction | HIGH | ≥ MEDIUM |

All 6 are available simultaneously via API (`GET /api/signals/scored/compare`).

---

## Slide 9 — Track Record

### Transparent, audited, bilingual

- **Live predictions** since March 2026 — evaluated at D+1 and D+5 by comparing predicted direction to actual close
- **60-day historical simulation** — same agent logic applied to past EGX prices, clearly tagged **SIM**
- **Walk-forward backtest** — re-runs every Sunday on all ~190 EGX stocks

**Key numbers (illustrative):**

| Metric | Value |
|---|---|
| Directional accuracy (D+1) | Tracked live |
| Average alpha vs EGX30 | Tracked live |
| Signals evaluated | Growing daily |
| Stocks covered | ~190 EGX listed |

Public URL — share directly with prospective investors: `/track-record`

---

## Slide 10 — ETF & Macro Intelligence

### Beyond single stocks

**EGX ETF Dashboard**
- 13 locally-listed Egyptian ETFs sourced from Mubasher (Arabic scraper)
- 4 global Egypt-focused ETFs (EGPT, EEMX, FM, FRDM) via yfinance
- NAV, premium/discount, holdings modal, PDF factsheet RAG search

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
GitHub Actions (cron)
        ↓
Python Agents (5 models + consensus)
        ↓
Execution Gate (friction + regime filter)
        ↓
PostgreSQL on Render.com
        ↓
Node.js/Express API
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

---

## Slide 13 — Competitive Positioning

| Feature | Xmore | Generic screeners | Broker platforms |
|---|---|---|---|
| EGX-specific signals | ✓ | Partial | ✗ |
| 5-agent consensus | ✓ | ✗ | ✗ |
| Friction-adjusted signals | ✓ | ✗ | ✗ |
| Public audited track record | ✓ | ✗ | ✗ |
| Arabic RTL interface | ✓ | Rare | Partial |
| Institutional metrics (EGX RF) | ✓ | ✗ | ✗ |
| ETF + macro intelligence | ✓ | Partial | ✗ |
| RAG document search | ✓ | ✗ | ✗ |
| Free tier | ✓ | Varies | ✗ |

---

## Slide 14 — Roadmap

### Near-term
- [ ] Real-time intraday signal updates (websocket feed)
- [ ] Push notifications (email / Telegram) when signal changes
- [ ] Options on EGX derivatives when exchange enables them
- [ ] Brokerage API integration (direct order placement)

### Medium-term
- [ ] Paid Pro tier with advanced screener and API access
- [ ] Portfolio optimiser (mean-variance, EGX constraints)
- [ ] Mobile app (React Native)
- [ ] Expansion to ADX (Abu Dhabi) and Tadawul (Saudi)

---

## Slide 15 — Summary

### Why Xmore

1. **Only** pre-market AI consensus engine built specifically for EGX
2. **Friction-realistic** — models actual Egyptian trading costs before recommending
3. **Fully bilingual** — Arabic-first in a market where Arabic dominates
4. **Institutionally measured** — EGX-correct risk metrics, public track record
5. **Open by design** — predictions and performance are public; trust is earned, not claimed
6. **Production-running** — live daily since March 2026, automated pipeline, zero manual intervention

> **Xmore turns Egypt's information asymmetry into a solvable engineering problem.**

---

*xmore-project.onrender.com · GitHub: crassdart85/xmore-v2*
