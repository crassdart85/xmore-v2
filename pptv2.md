# Xmore Investor Deck (PPT v3)

---

## 1. Title

**Xmore**
AI-powered Tadawul market intelligence and decision support

**Tagline:** Institutional-grade signals. Walk-forward validated. Built for Saudi Arabia.

---

## 2. The Problem

Saudi Arabia's retail and professional investors face a market intelligence gap:

- **No trusted signals** — recommendations are opaque, unaudited, and unexplained
- **Friction blindness** — tools ignore Tadawul costs (brokerage, VAT, exchange fees), and liquidity constraints
- **Language exclusion** — every professional-grade tool is English-only
- **Benchmark misuse** — Sharpe ratios calculated with US risk-free rates (5%) instead of SAIBOR 3M (4.89%), inflating apparent performance
- **No regime awareness** — systems publish buy signals during crisis periods; no market state gating
- **ETF blindspot** — Saudi-listed ETFs have zero quantitative signal coverage

---

## 3. The Solution

**Xmore** is a full-stack Tadawul intelligence platform that runs daily, automatically, and publicly audits every signal it publishes.

**Three core capabilities:**

1. **AI signal engine** — six heterogeneous agents, a four-layer consensus pipeline, regime gating, and walk-forward validation
2. **Institutional performance layer** — KSA-correct Sharpe/Sortino/Calmar with SAIBOR 3M risk-free rate; public track record with equity curve
3. **Market intelligence hub** — bilingual (EN/AR) dashboard with live briefing, ETF signals, pivot levels, AI research assistant, and macro analysis

---

## 4. Why Now

- Tadawul retail participation is accelerating — but tools remain fragmented and English-only
- CMA regulatory push for transparency and risk disclosure creates demand for auditable systems
- Arabic-first quantitative intelligence is effectively unserved
- ETF market on Tadawul is growing but has zero signal coverage today
- AI infrastructure costs have collapsed — what cost millions two years ago runs for hundreds per month

---

## 5. Product: The Signal Engine

**Six AI agents, four pipeline layers:**

| Agent | Method |
|---|---|
| ML Agent | Per-symbol LightGBM (Optuna-tuned, 25 trials) |
| MA Agent | Adaptive moving average crossover (vol-regime periods) |
| RSI Agent | Adaptive RSI (regime-adjusted overbought/oversold) |
| Volume Agent | Unusual volume detection and confirmation |
| Sentiment Agent | Gemini-powered news analysis with recency decay |
| Risk Agent | Volatility, GARCH forecast, position-size limits |

**Four-layer pipeline:**
1. **Agent vote** — weighted by live accuracy (dynamic weights updated daily)
2. **Confidence gating** — signals with < 60% max probability converted to HOLD
3. **Execution filter** — edge ratio must exceed 3× round-trip cost (Tadawul-specific costs: ~38.2 bps)
4. **Regime gate** — HMM-detected Crisis blocks UP signals; Turbulent downgrades conviction

**Coverage:** 50+ Tadawul-listed stocks + active ETFs

---

## 6. Product: Walk-Forward Validation

**The institutional standard. Not a backtest.**

| Simple Backtest (industry norm) | Walk-Forward (Xmore) |
|---|---|
| Trains and tests on the same historical data | Trains on 90 days, tests on next 20 it has never seen |
| Risk: memorising the past | Rolls forward in 10-day steps |
| Cannot distinguish signal from noise | True out-of-sample accuracy |
| Inflated accuracy figures | Conservative, defensible figures |

Walk-forward results run every Sunday and are published publicly on the Track Record page — per agent, per symbol — with no cherry-picking.

---

## 7. Product: ETF & ETP Signals

The first quantitative signal engine for Tadawul-listed funds.

**Signal components (per instrument, daily):**
- MA crossover (adaptive periods)
- RSI (adaptive period, oversold/overbought)
- **NAV premium/discount signal** — unique to fund instruments: trading at >2% discount to NAV → BUY signal; >3% premium → SELL
- 5-day momentum

**Instruments covered:** All active Tadawul-listed ETFs + regional KSA-focused ETFs

**Output:** UP / HOLD / DOWN signal with confidence %, individual sub-signal breakdown, and NAV premium/discount badge — displayed on Pro page and Track Record.

---

## 8. Product: Market Intelligence Hub

**Eight integrated modules:**

| Module | What it does |
|---|---|
| **Predictions Dashboard** | Daily signals for 50+ stocks — screener by signal, sector, conviction, confidence |
| **Market Regime Banner** | Live Calm / Turbulent / Crisis indicator on every page |
| **Daily Briefing** | 7-section pre-market brief: market pulse, actions today, portfolio snapshot, watchlist heatmap, sector breakdown, risk alerts, sentiment |
| **Session Sheet** | Intraday pivot levels (P/R1/R2/S1/S2), ATR, trend bias, position simulator |
| **Xmore Pro** | Professional view: top movers, sector performance, ETF signals, regime pill, macro analysis |
| **Time Machine** | Monte Carlo GBM forecast (pure JS, no Python) for any TASI stock or ETF |
| **AI Research Assistant** | Gemini RAG grounded in live prices, signals, regime state, backtest results, ETF NAV/AUM, news, and user portfolios |
| **Track Record** | Public audit: equity curve, signal distribution, sector accuracy, regime performance, walk-forward results, ETF signals, prediction log |

---

## 9. Proof of Edge — by Design

**Four layers of public accountability:**

1. **Immutable signal log** — every prediction timestamped before market open; exportable CSV
2. **Walk-forward validation** — out-of-sample accuracy published weekly per agent
3. **Benchmarking** — all metrics vs TASI; alpha and IR computed at D+1 and D+5
4. **Regime transparency** — accuracy broken down by Calm / Turbulent / Crisis regimes; regime gate performance shown explicitly

**Key metrics displayed publicly (no login required):**
- Win rate · Alpha · Sharpe · Sortino · Calmar · Max Drawdown · Information Ratio
- Sector accuracy leaders
- Agent accountability (per-agent accuracy, signal count, rolling performance)

---

## 10. Differentiation

| Dimension | Competitors | Xmore |
|---|---|---|
| **Signal methodology** | Black box | 6 agents, 4-layer pipeline, published weights |
| **Validation** | In-sample backtest | Walk-forward out-of-sample (institutional standard) |
| **Tadawul cost model** | None | Full round-trip cost (brokerage, VAT, exchange fees, slippage) |
| **Regime awareness** | None | HMM-gated: Crisis blocks UP; Turbulent downgrades |
| **Language** | English only | Full Arabic (RTL), bilingual across all 8 pages |
| **ETF coverage** | Price display only | Daily quantitative signals (MA, RSI, NAV premium) |
| **Transparency** | None | Public track record, immutable logs, exportable data |
| **Benchmark** | US risk-free rate | SAIBOR 3M rate (4.89%), 250 Tadawul trading days |

---

## 11. Architecture — Why It Works at Scale

**Python never runs at request time.**

All signal computation, model inference, performance metrics, ETF signal generation, and investor scoring run in GitHub Actions CI (scheduled jobs) and are written to PostgreSQL before any user loads a page.

- **API response time:** < 500 ms (p95) — all results pre-computed
- **Pipeline:** 7 scheduled CI jobs covering intraday, daily, and weekly workflows
- **Database:** 40+ tables; all writes are idempotent upserts
- **Failsafe:** Optional modules (ETF signals, news ingestion, scoring) wrapped non-fatally — partial results always better than zero
- **Cost:** Runs on Render.com + GitHub Actions free tier

---

## 12. Business Model

**SaaS + Enterprise Licensing**

| Tier | Target | What they get |
|---|---|---|
| **Free** | Retail investors | Full signal dashboard, track record, daily briefing, ETF signals |
| **Pro** | Active traders, advisors | Session sheet, advanced screener, AI assistant, Time Machine, portfolio tracking |
| **Team** | Research desks, fund managers | Multiple seats, private RAG knowledge base, custom data sources |
| **Enterprise** | Brokerages, asset managers | White-label, dedicated SLA, compliance artifacts, API access |

**Revenue paths:** Direct subscriptions + brokerage distribution partnerships + API licensing

---

## 13. Go-to-Market

- **Phase 1 (now):** Build track record with free tier — signal quality is the marketing
- **Phase 2:** Target 20 brokerages and advisory desks for Pro and Team pilots
- **Phase 3:** Enterprise rollout — brokerage white-label integration, API licensing for research platforms
- **Expansion path:** ADX (Abu Dhabi) → Tadawul (Egypt) — same architecture, new data sources

---

## 14. Moat

- **Local data pipelines** — Tadawul-specific data providers, Arabic news parsers, SAIBOR rate, live KSA price source
- **Tadawul cost model** — complete round-trip cost model that no generic platform has bothered to build for KSA
- **Regime-gated signals** — HMM-based market state detection baked into signal production
- **Walk-forward validation infrastructure** — weekly backtesting harness with out-of-sample results published publicly
- **ETF signal engine** — first quantitative signal system for Tadawul-listed funds (NAV premium/discount is an ETF-specific signal no stock screener provides)
- **Proprietary RAG corpus** — fund prospectuses, market reports, and news embedded and queryable
- **Bilingual financial terminology layer** — 50+ stock names, sector labels, and UI strings in Arabic; not translatable overnight

---

## 15. Traction (Insert Metrics)

- Active users: _
- Daily signals generated: 50+ stocks + ETFs
- Signal evaluations completed: _
- Pipeline uptime: _
- Walk-forward windows run: _

*(Insert live metrics here before presentation)*

---

## 16. Roadmap

**Next 6 months:**
- [ ] ETF ML models (LightGBM per-instrument) as ETF price history accumulates
- [ ] Push notifications (email) on signal changes: HOLD → BUY
- [ ] Paid Pro tier with API key access
- [ ] Direct brokerage API integration (order placement)

**6–18 months:**
- [ ] Portfolio optimiser (mean-variance, Tadawul constraints)
- [ ] Mobile app (React Native, same API)
- [ ] ADX / Tadawul expansion
- [ ] Tadawul derivatives signals when exchange enables them

---

## 17. Ask

**Strategic capital or partnerships to:**
- Scale data coverage and signal breadth (additional markets, deeper ETF data)
- Accelerate enterprise sales into brokerage platforms and advisory desks
- Fund the ML infrastructure for per-instrument ETF models
- Distribution into Tadawul brokerage apps as an embedded intelligence layer

---

## 18. Contact

**Xmore**
Business Partnerships: [add email]
Platform: xmore-ksa.onrender.com
Repository: github.com/crassdart85/xmore-v2
