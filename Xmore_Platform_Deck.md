# Xmore — AI-Powered Market Intelligence Platform
### Business Presentation Deck · March 2026

---

## SLIDE 1 — TITLE

# XMORE
## AI-Powered Stock Intelligence for the Saudi Exchange

**Predict. Track. Outperform.**

> Real-time AI consensus signals, portfolio analytics, and market intelligence
> built for Tadawul traders and investment professionals.

---

## SLIDE 2 — THE PROBLEM

### Saudi market investors lack institutional-grade tools

| Challenge | Current Reality |
|-----------|----------------|
| Signal overload | 190+ Tadawul stocks, no unified view |
| Lag in analysis | Manual research takes hours after close |
| No accountability | Predictions made with no outcome tracking |
| Data fragmentation | Prices, news, FX, ETFs — all separate tools |
| Language barrier | Most platforms are English-only |

> **The result:** Retail and professional investors make decisions on incomplete,
> delayed, or purely subjective information.

---

## SLIDE 3 — OUR SOLUTION

### One Platform. Five AI Agents. Zero Guesswork.

Xmore aggregates signals from **5 independent AI agents** into a single, audited
consensus — updated every trading day after market close.

```
Moving Average   →  ─┐
RSI Agent        →  ─┤
Volume Spike     →  ─┼──▶  CONSENSUS  ──▶  Xmore Score (0–100)
Random Forest ML →  ─┤
Gemini LLM       →  ─┘
```

**Every signal is back-tested. Every prediction is evaluated against actual prices.**

---

## SLIDE 4 — XMORE SCORE

### A Single Number That Captures Market Conviction

| Score Range | Classification | Meaning |
|------------|---------------|---------|
| 75 – 100 | **VERY HIGH** | Strong multi-agent bullish alignment |
| 60 – 74 | **HIGH** | Majority of weighted agents bullish |
| 40 – 59 | **MODERATE** | Mixed signals, monitor closely |
| < 40 | **LOW** | Bearish pressure dominant |

- Composite of: bull ratio (30%), bear inverse (25%), agent agreement (25%), avg confidence (20%)
- Updated daily after Tadawul close
- Color-coded throughout the platform: **green ≥ 70**, **red < 45**

---

## SLIDE 5 — PREDICTIONS TAB

### Daily AI Signals for Every Tracked Stock

**What you see each morning before market open:**

| Symbol | Signal | Confidence | Xmore Score | Agents | Price (SAR) |
|--------|--------|-----------|-------------|--------|-------------|
| COMI | **BUY** | 87% | 78 | 4 / 5 | 62.40 |
| EKHW | **BUY** | 72% | 66 | 3 / 5 | 18.90 |
| HRHO | HOLD | 55% | 50 | 2 / 5 | 9.15 |
| ORWE | **SELL** | 68% | 32 | 3 / 5 | 4.30 |

**Screener controls:** Filter by signal · Confidence threshold · Sector · Volume
**Bilingual:** Full Arabic / English toggle with RTL layout

---

## SLIDE 6 — STOCK COMPARISON TOOL *(New)*

### Side-by-Side Multi-Stock Analysis in Seconds

Compare up to **4 Tadawul stocks simultaneously** across all AI dimensions:

- Consensus signal & confidence
- Xmore Score (bull pressure index)
- Bull / Bear ratio breakdown
- Last price in SAR
- One-click **AI Brief** for each stock

**Use case:** Portfolio manager screening sector rotation — compare COMI vs QNBE vs CIEB
before committing capital, in one modal, without switching tabs.

---

## SLIDE 7 — PER-STOCK AI BRIEF *(New)*

### 3-Sentence Gemini Analyst Narrative — On Demand

Every stock generates a structured brief covering:

1. **Stance** — current signal, confidence level, which agents agree
2. **Key Risk** — primary downside scenario for the 5-day horizon
3. **Outlook** — price levels to watch, volume profile commentary

> *"COMI carries a strong BUY signal with 87% confidence, underpinned by bullish
> MA crossover alignment and elevated RSI momentum — 4 of 5 agents agree on the
> upside case..."*

- Powered by **Gemini 2.5 Flash**
- Cached 1 hour to minimize API cost
- Accessible from Comparison Tool & individual stock rows

---

## SLIDE 8 — VIRTUAL PORTFOLIO

### Full SAR Portfolio Tracking with Live P&L

**Real-time accounting for every position:**

| Feature | Detail |
|---------|--------|
| Position tracking | Symbol, entry price, quantity, entry date |
| Live P&L | Cost SAR vs. current market value SAR |
| Trade history | All closed trades with win rate + avg return |
| Sector allocation | Visual bar chart — concentration risk at a glance |
| Totals strip | Invested / Market Value / P&L (SAR) / Return % |

**Add a trade in 3 clicks.** Close with a single entry. All calculations are automatic.

---

## SLIDE 9 — PRICE ALERTS *(New)*

### Automated Threshold Monitoring — No Background Job Required

Set **above / below** price alerts for any Tadawul stock:

- Alert fires when current price crosses your target
- Checked automatically when Portfolio tab loads
- Current live price shown on every alert row
- Up to **20 active alerts** per user account

**Example:** Alert on COMI above 64.00 SAR — catch breakouts without watching a screen all day.

> Alerts are stored per user. No SMS or email push yet — notification appears inline
> when you open the platform.

---

## SLIDE 10 — RATES TAB *(New)*

### Live FX & Gold Intelligence for Tadawul Context

**Live rate cards updated on every page load:**

| Rate | Description |
|------|-------------|
| USD / SAR | Saudi Riyal exchange rate |
| USD / SAR | Saudi Riyal for cross-border investors |
| SAR / SAR | Direct SAR conversion |
| XAU / USD | Spot gold price (troy oz) |
| Gold 24K / gram (SAR) | Retail gold benchmark |
| Gold 21K / gram (SAR) | Most common Saudi jewelry standard |
| Gold Pound (SAR) | 8g of 21K — Saudi investor benchmark |

**90-day sparkline history** charts for each rate — auto-accumulating daily record.

---

## SLIDE 11 — PERFORMANCE DASHBOARD

### Every Prediction Is Measured. Every Agent Is Accountable.

**Agent accuracy leaderboard (live example):**

| Agent | Accuracy | Evaluated |
|-------|---------|-----------|
| Gemini LLM | **73%** | 310 predictions |
| Random Forest | 69% | 310 predictions |
| RSI Agent | 62% | 310 predictions |
| MA Crossover | 61% | 310 predictions |
| Volume Spike | 58% | 310 predictions |

**Agents with declining accuracy are detectable early** — the platform surfaces
underperformance before it affects your capital.

---

## SLIDE 12 — MULTI-HORIZON SIGNAL EVALUATION *(New)*

### Signals Tested at D+5, D+10, and D+20

Not all stocks respond on the same timeline. Xmore now evaluates every consensus
signal at **three horizons**:

| Horizon | Trading Days | Use Case |
|---------|-------------|---------|
| D+5 | 1 week | Short-term swing traders |
| D+10 | 2 weeks | Medium-term position sizing |
| D+20 | 1 month | Trend confirmation, longer holds |

> Example: COMI D+10 accuracy = **81%** across 16 evaluated predictions
> — the signal holds at medium-term horizons, giving confidence to size up.

---

## SLIDE 13 — FORECAST PORTFOLIOS

### Build a Scenario. Track It Against Reality.

Create a **named portfolio** with a custom horizon and Xmore forecasts expected
return for each position using all active agents:

**Six horizons available:** 1m · 2m · 3m · 6m · 1yr · 2yr

**What you get:**
- Per-stock forecast return %
- Daily actual price recording
- Forecast vs. actuals chart overlay
- Business narrative: phase (early/mid/late), gap to forecast, beat count

> *"Aggressive Q2 — Phase: mid (day 21 of 42). Average actual vs forecast gap:
> +1.8 pp ahead. 2 of 3 positions beating forecast."*

---

## SLIDE 14 — ETF DASHBOARD

### Tadawul and Global Egypt-Focused ETFs in One View

**Local Tadawul ETFs (via Mubasher):**
- ~14 funds tracked including equity, commodity, and balanced funds
- Price, NAV, premium/discount, fund volume
- Holdings modal with top positions and weights

**Commodity ETPs** *(New)*:
- Gold and commodity trackers now classified separately
- Dedicated ETPs tab for quick filtering

**Global ETFs (NYSE/NASDAQ):**
- SART, EEMX, FM, FRDM — Egypt-exposure funds
- Daily price, change %, volume
- Country exposure breakdown

---

## SLIDE 15 — XMORE PRO DASHBOARD

### Professional Terminal for Serious Investors

Standalone screen at `/pro` — designed for all-day market monitoring:

| Module | Description |
|--------|-------------|
| Tadawul Advanced Chart | TradingView TASI live area chart |
| Market Movers Table | Top Tadawul blue chips with live consensus |
| Top Gainers / Losers | 8-row session leaderboards |
| Sector Performance | Horizontal P&L bars per sector |
| FX Strip | Live USD/SAR, USD/SAR, SAR/SAR in header |
| Macro Brief | Gemini-grounded Saudi economy overview |
| Walk-Forward Backtest | Historical directional accuracy per stock |

**Fully bilingual — English / Arabic RTL.**

---

## SLIDE 16 — MACRO BRIEF

### Real-Time Saudi Economy Intelligence

Powered by **Gemini 2.5 Flash with Google Search Grounding** (not training data):

- TASI index level and trend
- USD/SAR current rate
- Inflation and interest rate context
- Key session movers and macro catalysts
- **3 clickable web source citations** per brief

**Auto-loads on Pro page open. Refreshes every 60 minutes.**
Available via one-tap "📊 Macro Brief" chip in the Market Assistant chat.

---

## SLIDE 17 — MARKET ASSISTANT

### AI Chat with Full Market Context Injection

Every message sent to the assistant is pre-loaded with:

- Today's top gainers / losers
- Volume leaders
- Sentiment scores per stock
- Consensus signals for all tracked equities
- ETF prices
- **Your personal forecast portfolios** (when signed in)

**Quick chips for common queries:**
`📊 Macro Brief` · `📈 Top Movers` · `🎯 Buy Signals`

Arabic-aware — keyword extraction works in both languages.

---

## SLIDE 18 — TIME MACHINE

### Replay Any Past Tadawul Session

Select any historical trading date to see:

- What the AI agents predicted that day
- Actual price outcomes (green ✓ / red ✗)
- Session-level accuracy, best/worst calls
- Per-agent win rate for that specific date

**Use case:** Strategy review — understand which market conditions the AI models
excel or struggle in before increasing position sizes.

---

## SLIDE 19 — WALK-FORWARD BACKTEST

### Statistical Confidence Before You Commit Capital

Every Sunday, a walk-forward backtest runs across all tracked Tadawul stocks:

| Metric | What It Measures |
|--------|-----------------|
| Accuracy | Overall directional correctness |
| Directional Accuracy | BUY/SELL hit rate |
| Signal P&L % | Hypothetical return following signals |
| Max Drawdown | Worst peak-to-trough loss |

Results displayed in **Xmore Pro** sorted by directional accuracy — quickly identify
which stocks the models predict most reliably.

---

## SLIDE 20 — PLATFORM ARCHITECTURE

### Enterprise-Grade, Zero Maintenance

| Layer | Technology | Notes |
|-------|-----------|-------|
| Frontend | Vanilla JS, Bloomberg-style UI | No framework dependency |
| Backend | Node.js / Express | REST API, JWT auth |
| AI Agents | Python (5 agents) | Runs on GitHub Actions |
| Database | PostgreSQL (Render) | Auto-backup, 99.9% uptime |
| LLM | Google Gemini 2.5 Flash | Grounded web search |
| Deployment | Render.com + GitHub Actions | Auto-deploy on every push |
| Scheduling | GitHub Actions cron | 8 scheduled jobs |

**Fully cloud-hosted. No on-premise infrastructure required.**

---

## SLIDE 21 — AUTOMATION SCHEDULE

### Data Pipeline Runs Automatically — Every Trading Day

| Job | Time (Riyadh) | Function |
|-----|-------------|----------|
| Intraday Prices | 09:00–14:00 | Live price updates during session |
| News Collection | 09:00 / 11:00 / 13:00 | Headlines + RSS ingestion |
| Post-Market Pipeline | 14:30 | Close prices → sentiment → agent signals |
| Tadawul Snapshot | 16:00 | Full daily data export |
| Nightly Pipeline | 00:00 | AI briefs, portfolio updates |
| ETF Collection | 15:30 | Tadawul ETF prices, NAV, holdings |
| Global ETF Prices | 23:30 | NYSE/NASDAQ ETF data |
| Weekly Backtest | Sunday 09:00 | Walk-forward accuracy run |

**Zero manual intervention required after setup.**

---

## SLIDE 22 — SECURITY & ACCESS

### Multi-Layer Authentication

| Layer | Mechanism |
|-------|----------|
| User accounts | Email + password, JWT in HTTP-only cookie |
| Portfolio & alerts | Per-user, session-gated |
| Admin panel | Separate ADMIN_USERNAME + ADMIN_PASSWORD |
| API endpoints | Bearer token for admin operations |
| Database | Environment-variable credentials, SSL enforced |

**Bilingual access:** Full Arabic UI with RTL layout for MENA investor base.
**Responsive:** Mobile-optimised — works on phone, tablet, and desktop.

---

## SLIDE 23 — ADMIN PANEL

### Full Operational Control

| Tab | Function |
|-----|---------|
| System Health | DB row counts, agent status, pending jobs |
| Knowledge Base | Upload PDF/image market reports (up to 25MB) |
| Reports | All documents with extraction status + AI insight |
| Ask Reports | Semantic RAG search across embedded reports |
| Prices | Manual price entry / override |
| News Sources | Manage RSS and news feeds |
| ETF Documents | Factsheet RAG status and embedding jobs |
| API Reference | Full REST endpoint reference |
| Settings | Platform configuration |

---

## SLIDE 24 — COMPETITIVE POSITIONING

### Where Xmore Sits in the Market

| Capability | Bloomberg Terminal | Reuters Eikon | Local Broker Apps | **Xmore** |
|-----------|-------------------|--------------|------------------|-----------|
| Tadawul AI Signals | ✗ | ✗ | ✗ | ✅ |
| 5-Agent Consensus | ✗ | ✗ | ✗ | ✅ |
| Signal Outcome Tracking | ✗ | ✗ | ✗ | ✅ |
| Arabic UI (full RTL) | Partial | Partial | Some | ✅ |
| Tadawul ETF + Gold Rates | Partial | Partial | ✗ | ✅ |
| Forecast Portfolios | ✗ | ✗ | ✗ | ✅ |
| Monthly Cost | $2,000+ | $1,800+ | Free | **Fraction** |

---

## SLIDE 25 — TARGET USERS

### Who Uses Xmore

**Individual investors**
Daily signal review before market open. Portfolio tracking in SAR. Price alerts.

**Fund managers & analysts**
Multi-stock comparison. Sector performance. Walk-forward backtest confidence metrics.
Macro brief for client reporting.

**Research teams**
Ask Reports RAG — query PDF research directly. AI briefs for quick stock summaries.
Multi-horizon accuracy to validate model assumptions.

**Traders**
Session Sheet with pivot levels, candlestick patterns, ATR. Time Machine for
strategy review. Intraday price updates.

---

## SLIDE 26 — ROADMAP HIGHLIGHTS

### What's Live vs. Coming

**Live Today**
- ✅ 5 AI agents + Xmore Score
- ✅ Bloomberg-style terminal UI
- ✅ Forecast portfolios with D+5/10/20 evaluation
- ✅ ETF dashboard (Tadawul + Global)
- ✅ Commodity ETPs tab
- ✅ FX + Gold rates with 90-day history
- ✅ Price alerts, Stock comparison, AI briefs
- ✅ Walk-forward backtest
- ✅ Macro brief (grounded web search)
- ✅ Market assistant chat
- ✅ Bilingual EN/AR full RTL

**Potential Next Steps**
- ☐ Push notifications (email / Telegram) for price alerts
- ☐ Broker API integration for real trade execution
- ☐ Expanded universe: Saudi Tadawul, ADX
- ☐ White-label version for institutional clients

---

## SLIDE 27 — CLOSING

# XMORE
## The Intelligence Layer for Tadawul Investors

**5 AI agents. Daily signals. Full accountability.**

Live at: **xmore-project.onrender.com**
Pro terminal: **/pro**
Documentation: **/docs**

---

*Xmore — AI Stock Prediction for Tadawul & Global Markets*
*© 2026 — Confidential business presentation*
