# Xmore — AI Stock Intelligence for the Saudi Exchange
### Simple Guide · Platform Walkthrough · Key Features

---

## What Is Xmore?

Xmore is an AI-powered stock intelligence platform built specifically for the **Saudi Exchange (Tadawul)** — the largest exchange in the Middle Easttock market open Sunday–Thursday, 10:00–14:30 Riyadh time.

**The problem it solves:**
Saudi retail investors have almost none of the analytical tools available in US or other markets. No Arabic-language screener, no sentiment tool that reads Arabic news, no system to tell you when the market regime has quietly shifted from calm to turbulent. Most traders rely on tips and gut feel.

**What Xmore does:**
Every day before the market opens, five independent AI agents analyze every tracked KSA stock — reading prices, news (Arabic + English), technical patterns, and macro signals — and vote on whether each stock is likely to go **UP**, **DOWN**, or **HOLD**. The votes are weighted by each agent's recent accuracy, risk-checked, filtered for market regime, and published as a final confident signal with a conviction percentage. No backdating. No cherry-picking. Every signal is timestamped before market open.

---

## The Five AI Agents

| Agent | What it does |
|---|---|
| **ML (LightGBM)** | Learns price-pattern features per stock; retrained weekly; confidence gates: <60% → becomes HOLD |
| **RSI** | Mean-reversion momentum; adapts period to market volatility (high vol = longer period) |
| **Moving Average** | Trend crossover (short vs long MA); also adapts to volatility regime |
| **Sentiment** | Reads Arabic + English news via Gemini AI; recency-decayed (yesterday's news counts less) |
| **Volume** | Detects unusual volume spikes signalling institutional activity |

These five agents vote. A **Consensus Engine** weighs their votes by recent accuracy, applies a risk filter, then applies a **Regime Gate**: if the market is in "Crisis" mode (Hidden Markov Model), all UP signals are blocked market-wide.

---

## Creating Your Account

**Get started in under 30 seconds:**

1. Click **"🔐 Login / Sign Up"** on any page (top-right corner)
2. Switch to the **Sign Up** tab
3. Enter your **email** and a **password** (8+ characters)
4. Click **Sign Up** — you're logged in immediately

**What you unlock with an account:**

| Feature | Without account | With account |
|---------|----------------|--------------|
| Predictions, Briefing, Pro page | ✅ Full access | ✅ Full access |
| Track Record | ✅ Full access | ✅ Full access |
| Time Machine | ✅ Full access | ✅ Full access |
| Watchlist (filter everything to your stocks) | ❌ | ✅ |
| Portfolio & Forecast tracking | ❌ | ✅ |
| Session Sheet (daily pivot levels + trade ideas) | ❌ | ✅ |
| My Forecast Portfolio on Pro page | ❌ | ✅ |
| AI Research Assistant (personalised answers) | ❌ | ✅ |

**Security:**
- Passwords hashed with bcrypt (12 rounds) — never stored in plaintext
- Login rate-limited to 5 attempts per minute per IP
- Bilingual interface (EN / عربي) — toggle anytime from the header

> **Tip:** After signing up, immediately add stocks to your **Watchlist** — every tab then filters to show only your stocks for a personalised experience.

---

## How to Use the Website

**The main dashboard** is at the home URL. It has **13 tabs** across the top:

| Tab | Use it when… |
|---|---|
| **Predictions** | You want today's BUY/SELL/HOLD for all KSA stocks |
| **Briefing** | You want the daily 7-section AI morning report |
| **Trades** | You want specific trade ideas for the session |
| **Watchlist** | You want to filter everything to only your followed stocks |
| **Portfolio** | You want to track open positions and P&L |
| **Forecasts** | You want to run Monte Carlo projections |
| **Consensus** | You want to see how each agent voted on a signal |
| **Performance** | You want historical accuracy metrics and equity curve |
| **Results** | You want to verify whether past signals were correct |
| **Prices** | You want a quick price/volume table |
| **Time Machine** | You want to replay the past OR simulate the future |
| **Rates** | You want USD/SAR and gold prices |
| **ETFs** | You want technical signals on KSA funds |

**Tip:** Create an account and add stocks to your **Watchlist** — every tab then filters to show only your stocks, so you get a personalized experience.

---

## Daily Market Briefing

Before you do anything else each day, open the **Briefing** tab. It loads a fresh AI-generated morning report with seven sections:

1. **Market Pulse** — Is the market broadly bullish, bearish, or mixed today? Breadth, volume vs yesterday, top movers.
2. **Your Actions Today** — Any urgent BUY or SELL signals specifically for stocks you follow.
3. **Portfolio Snapshot** — Quick P&L read on your open positions.
4. **Watchlist Signal Map** — Visual heatmap of your stocks sorted by signal strength.
5. **Sector Overview** — How each of the KSA sectors is positioned today.
6. **Risk Alerts** — Signals that were downgraded or blocked by the risk filter.
7. **Sentiment Snapshot** — Overall positive/negative split from Arabic + English news today.

Think of this as your **60-second morning brief** before making any trading decision.

---

## ⏱️ TIME MACHINE (Deep Dive)

The Time Machine tab has two distinct tools: **Past** and **Future**.

---

### Time Machine — Past Tab: "What if I had invested here?"

**In plain language:** You pick a past date and an amount in SAR. The system replays exactly what Xmore's historical trading signals would have done with your money from that date until today. You see whether you would have made or lost money, and how that compares to simply buying the TASI index.

**Step-by-step:**

1. **Set your amount** — Use the slider or type directly. Range: 5,000 SAR to 10,000,000 SAR.
2. **Pick your start date** — Or use the quick buttons: 3 months ago, 6 months ago, 1 year ago, 2 years ago.
3. **Click Simulate** — Wait a few seconds while the system replays history.

**What you see:**

| Result | What it means |
|---|---|
| **Hero card** | Your 50,000 SAR → 68,420 SAR with +36.8% return animated in real time |
| **Alpha vs TASI** | How much Xmore beat the index — e.g. +12pp above the market |
| **Equity curve chart** | Your portfolio (blue filled area) vs TASI benchmark (grey dashed line) over time |
| **Monthly breakdown table** | Month-by-month comparison: Xmore % vs TASI % |
| **Top winning trades** | The best individual trade calls in that period, with entry/exit prices and profit in SAR |
| **Worst losing trades** | The bad calls — shown honestly, not hidden |
| **Trade timeline** | Every BUY and SELL event in chronological order with the reason |

**Why it matters:** This is not a backtest you cherrypicked — it replays exactly what the live signal engine would have said on those real dates. The benchmark comparison makes the value proposition clear.

---

### Time Machine — Future Tab: "What might happen if I invest now?"

**In plain language:** You pick a stock (or let the AI pick for you), an investment amount, a target date, and a market scenario. The system runs **5,000 simulations** of possible futures using a Monte Carlo model calibrated to that stock's historical volatility and trend. You get a probability distribution of outcomes — not a single prediction, but a realistic range.

**Two modes:**

**Auto — AI picks the best stock for you:**
1. Set amount, target date (up to 30 days out), and scenario (Base / Bull / Bear).
2. The AI scans all KSA universe stocks and picks the one with the best expected return for your parameters.
3. You see a ranked list of all 30 stocks so you can review the AI's reasoning.

**Manual — You pick your own stocks:**
1. Set amount, horizon, and scenario.
2. Search for stocks by name or ticker and add up to 20 as colored pills.
3. Compare them side-by-side in a ranked table.

**What you see (single stock):**

| Result | What it means |
|---|---|
| **Expected portfolio value** | e.g. "Your 50,000 SAR is expected to become 56,200 SAR" — animated counter |
| **Probability of profit** | e.g. "67% chance your investment will be positive" — shown as a progress bar |
| **Scenario range** | Worst case (5th percentile) / Median / Best case (95th percentile) — three side-by-side values |
| **Band chart** | Green dashed = best path, blue filled = median, red dashed = worst, grey line = break-even |
| **Outcome histogram** | Distribution of all 5,000 simulation final values — green bars = profit, red bars = loss |
| **Plain-language summary** | "Based on 5,000 simulations, 2222.SR is expected to return +12.4% over 63 trading days." |

**Three scenarios explained:**
- **Base** — neutral market assumptions using historical drift
- **Bull** — applies an optimistic drift boost (models a favorable macro environment)
- **Bear** — applies a pessimistic drag (models headwinds, rising rates, risk-off)

**Why it matters:** You are not getting a single-point prediction ("the stock will go up"). You are getting an honest range of outcomes, a probability distribution, and the worst-case number you need to know before you invest.

---

## 📊 PRO PAGE (Deep Dive)

The Pro page (`/pro`) is a market-intelligence dashboard for active traders who want a single, data-rich view of the **entire Tadawul market** — not just their own watchlist.

**Header bar (always visible):**
- Live FX rates: USD/SAR — updated hourly
- Gold prices in SAR per gram: 24K, 21K, 18K
- Today's date (day of week + calendar date)

**TradingView live ticker tape:**
A scrolling live feed of real prices for TASI, Aramco, Al Rajhi, STC, and 8 other major blue chips — running along the top of the page from TradingView. Prices are real-time.

---

### Pro Page Sections

**1. Market Stat Pills**

Six summary numbers across the top that tell you the market state in under five seconds:

| Pill | What it shows |
|---|---|
| TRACKED | How many KSA stocks are being monitored by Xmore |
| UP | Stocks advancing today + what percentage of the market they represent |
| DOWN | Stocks declining today |
| BEST AGENT WIN RATE | Highest accuracy % among all individual AI agents in recent history |
| LAST DATA | Date of the most recent price data loaded |
| MARKET REGIME | **Calm** (green) / **Turbulent** (amber) / **Crisis** (red) — from the HMM model |

**2. TASI Intraday Chart + Blue Chips**

Split view:
- **Left:** A full TradingView advanced candle chart of the TASI index (5-minute candles, Riyadh timezone)
- **Right:** A TradingView market overview widget showing major KSA blue chips with their day-change %

**3. Top Gainers and Top Losers Tables**

Two side-by-side tables, each showing the 8 biggest movers. Columns:

| Column | Meaning |
|---|---|
| Symbol | Ticker (.SR) |
| Close | Latest price |
| Change % | Day's gain or loss — green or red |
| Signal | BUY / SELL / HOLD badge from the consensus engine |
| Confidence | How certain the AI is about the signal (%) |
| Xmore Score | 0–100 composite (70+ = green, below 45 = red) |

**Why it's useful:** A stock that is up 4% today but has a SELL signal at 75% confidence is a potential short opportunity — or a warning to take profits.

**4. Sector Performance Panel**

Horizontal bar chart for every KSA sector. Green = sector average up, red = down. Tells you instantly which sectors are rotating in or out of favor today — which helps portfolio-level decisions.

**5. ETF and ETP Signals**

Cards for every tracked KSA fund and commodity tracker. Each card shows:
- Signal badge (UP / DOWN / HOLD)
- Confidence %
- RSI value
- **NAV premium or discount %** — buying an ETF trading at a 4% premium is risky because prices tend to revert toward the net asset value

**6. My Forecast Portfolio (logged-in users)**

If you have created forecast portfolios on the main dashboard, this section shows real-time performance tracking:
- Avg AI forecast return vs avg actual return so far
- Portfolio progress bar (e.g. "17 of 30 trading days elapsed — 57%")
- Per-stock bar chart: purple bar = AI forecast, green/red bar = actual so far
- Plain-language summary auto-generated, e.g. "7 of 10 positions are meeting or beating their AI targets"

**7. Derivatives Brief Panel**

Quick Black-Scholes options calculator:
- Input: ticker, spot price, strike, expiry (1M / 3M / 6M / 1Y)
- Output: Call price, Put price, Straddle cost, Delta, Gamma, Theta/day, Vega/1% vol — all in SAR
- Useful for quickly checking hedge cost before opening or exiting a large position

**8. Walk-Forward Backtest Results**

A table showing the ML agent's out-of-sample accuracy per stock (90-day train / 20-day test, rolling forward, recalculated every Sunday). Columns: Symbol, Accuracy %, Directional Accuracy %, Signal P&L %. This is the evidence base for whether the AI has real edge — not in-sample curve fitting, but on data the model never saw during training.

**9. Macro Brief Panel**

An AI-generated narrative (auto-refreshed hourly) covering:
- SAMA repo rate direction and implication for KSA valuations
- IMF program status and FX confidence signal
- Current USD/SAR level
- Global shocks (oil, EM risk-off, regional events)
- Which KSA sectors have a tailwind vs headwind today
- Net macro tone: supportive / neutral / cautious

Powered by Gemini with Google Search grounding — the AI actually searches the web in real time for current SAMA and IMF data.

---

## 📋 SESSION SHEET (Deep Dive)

The Session Sheet (`/session`) is a **pre-market cheat sheet** designed to be read in the 15–30 minutes before Tadawul opens (before 10:00 Riyadh time, Sunday–Thursday). Login is required.

---

### Index Support & Resistance Cards

At the top, cards for the **TASI** and **Nomu** indices show the six key levels computed from the previous session's OHLC data:

| Level | What it means |
|---|---|
| **S2** | Second support — deeper floor if S1 breaks |
| **S1** | First support — nearest price floor |
| **Pivot** | Classic floor-trader pivot point |
| **R1** | First resistance — nearest price ceiling |
| **R2** | Second resistance — higher ceiling if R1 breaks |
| **Stop Loss** | Where to exit an index ETF position if it breaks down |

Use these to set intraday price alerts, or to decide whether the index is likely to bounce or break at key levels during the session.

---

### Stock Signals Table

The main table lists every stock with a trade recommendation for today's session. Columns:

| Column | What it means |
|---|---|
| **CODE** | Ticker symbol |
| **Name** | Company name (English or Arabic based on language toggle) |
| **Trend** | 🟢 **Bullish** / ⬜ **Sideways** / 🔴 **Bearish** |
| **Type** | **Trade** (short-term momentum) or **Hold** (longer-term position) |
| **Buy Guide** | Recommended entry price (set at the S1 support level) |
| **Stop Loss** | Exit price if the trade goes wrong |
| **Target** | Price target if the trade works |
| **Profit %** | % gain from Buy Guide to Target |
| **Risk %** | % loss from Buy Guide to Stop Loss |
| **R/R** | Risk/Reward ratio — ideally **≥ 2.0** |
| **S2, S1, Pivot, R1, R2** | Support and resistance levels for that specific stock |
| **Patterns** | Detected candlestick patterns (Hammer, Doji, Engulfing, etc.) — green = bullish, red = bearish |

**How to use this table in practice:**
Filter for stocks where all four conditions hold:
1. **Trend = Bullish** (green)
2. **Type = Trade** (short-swing setup)
3. **R/R ≥ 2.0** (reward is at least twice the risk)
4. **Bullish candle pattern present** (confirms the signal)

That combination is a high-conviction setup for the session.

---

### Virtual Portfolio Simulator

Below the main table is a paper-trading simulator — no real money involved:

1. Select a stock from the session sheet
2. Enter your entry price
3. Click "Open Position" — the trade is recorded
4. Watch real-time unrealized P&L update as prices change
5. Click "Close" when you want to exit — enter a price and the result is saved

A summary at the bottom tracks: total closed trades, win rate %, and average return %. Use this to build intuition about whether the Buy Guide and Target levels are realistic before putting real capital to work.

---

### Language Support

The entire Session Sheet (and indeed the whole platform) is fully bilingual:
- Click the **Arabic / English** toggle in the header
- Every label, column header, trend badge (صاعد / عرضى / هابط), and recommendation type (متاجرة / احتفاظ) switches language
- The page layout flips to right-to-left in Arabic mode

---

## Track Record — Accountability at the Core

The Track Record page (`/track-record`) is Xmore's public proof of edge. Every signal is shown — whether it was right or wrong. Nothing is removed or backdated.

Key sections:
- **KPI Summary** — Total signals, Win rate, Alpha vs TASI, Sharpe ratio, Profit factor (toggle: 30D / 90D / 180D / All-time)
- **Live Signal Feed** — The 20 most recent signals with timestamps proving they were issued before market open
- **Equity Curve** — Cumulative AI return (blue) vs TASI benchmark (grey)
- **Agent Breakdown** — Which agent is doing the heavy lifting right now
- **Sector Accuracy** — Where the AI has an edge and where it doesn't
- **Regime Performance** — Accuracy in Calm vs Turbulent vs Crisis markets (proves regime gating works)
- **Walk-Forward Validation** — Out-of-sample test results per stock (institutional-grade, not overfitted)
- **Full signal log** — Every prediction ever made, exportable as CSV, immutable after issuance

---

## The AI Research Assistant

Available in the dashboard and Pro page, the chat assistant knows:
- All KSA universe stocks by name (Arabic + English), sector, and ticker
- KSA market facts: trading hours (Sun-Thu 10:00-15:00 Riyadh), currency (SAR), TASI index, CMA regulator
- Live market data: today's gainers/losers, consensus signals, sentiment
- Current market regime
- The last week of news (Arabic + English sources)
- Your forecast portfolios (when logged in)
- Uploaded PDF reports and factsheets (RAG vector search)
- ETF prices, NAV, AUM, and signals

Ask it: "Why does 2222.SR have a BUY signal today?", "Which sectors have a tailwind?", "What is my portfolio doing vs the forecast?", "What is the current USD/SAR rate and what does it mean for Tadawul banks?" — and get a grounded, factual answer with cited sources.

---

## Quick-Start Checklist

```
□ 1. Sign up at the home URL
□ 2. Add your stocks to the Watchlist
□ 3. Every morning: open Briefing tab — read the 7-section report
□ 4. Before 10:00 AM: open Session Sheet — note Buy Guide, Stop Loss, Target for your stocks
□ 5. Check Pro page: confirm market regime, review top movers and sector rotation
□ 6. Use Predictions tab: find stocks where signal = BUY, confidence > 65%, type = Trade
□ 7. Use Time Machine (Future): simulate your shortlisted stock under Base / Bull / Bear scenarios
□ 8. Before committing capital: check Track Record for that stock's historical accuracy
□ 9. After the session: log paper trades in Session Sheet simulator to track performance
□ 10. Weekly: review Time Machine (Past) — did following the signals beat TASI?
```

---

## Key Facts at a Glance

| Item | Detail |
|---|---|
| **Exchange** | Saudi Exchange (Tadawul) — البورصة المصرية |
| **Trading days** | Sunday – Thursday |
| **Hours** | 10:00 – 14:30 Riyadh time (UTC+3) |
| **Currency** | Saudi Riyal (SAR) |
| **Main index** | TASI — 30 most liquid stocks |
| **Stocks tracked** | ~190 across 15 sectors |
| **Symbol format** | TICKER.SR (e.g. 2222.SR for Aramco) |
| **Signal freshness** | Agents run daily post-market; signals published before next open |
| **Languages** | English + Arabic (full RTL support) |
| **Data refresh** | Prices: intraday (6× daily during session) · News: 3× daily · Signals: once daily post-market |

---

*Xmore — AI-generated signals. Not financial advice. Always manage your own risk.*
