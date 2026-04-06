# Xmore — AI Stock Prediction System: User Manual

---

## Deployment Note

This manual describes the intended KSA product surface. On the live KSA deployment, some sections depend on the KSA data pipeline being healthy before they display populated content.

Data-dependent areas include:

- main dashboard stats
- `/pro`
- track record metrics and equity curve
- ticker tape and freshness indicators
- valuation and ETF modules

If those areas render empty, the usual cause is missing or stale KSA rows in the production database rather than a browser-side issue.

## Table of Contents

1. [Getting Started](#1-getting-started)
2. [Main Dashboard](#2-main-dashboard)
3. [Predictions Tab](#3-predictions-tab)
4. [Briefing Tab](#4-briefing-tab)
5. [Trades Tab](#5-trades-tab)
6. [Portfolio Tab](#6-portfolio-tab)
7. [Watchlist Tab](#7-watchlist-tab)
8. [Consensus Tab](#8-consensus-tab)
9. [Performance Tab](#9-performance-tab)
10. [Results Tab](#10-results-tab)
11. [Prices Tab](#11-prices-tab)
12. [Account & Settings](#12-account--settings)
13. [Admin Dashboard](#13-admin-dashboard)
14. [Bilingual Support](#14-bilingual-support)
15. [Keyboard & Accessibility](#15-keyboard--accessibility)

---

## 1. Getting Started

### 1.1 Accessing the Dashboard

Open the Xmore dashboard in any modern browser. No installation is required. The dashboard is fully responsive and works on desktop, tablet, and mobile.

Primary KSA routes in scope:

- `/`
- `/pro`
- `/track-record`
- `/docs`

### 1.2 User Roles

| Role | Access |
|------|--------|
| **Public (Guest)** | View predictions, consensus, results, prices, performance metrics, and market briefing (public sections) |
| **Logged-in User** | Everything above, plus: watchlist, today's trade recommendations, portfolio tracking, and personalized briefing sections |
| **Admin** | Everything above, plus: system health monitoring, audit logs, and knowledge base upload |

### 1.3 Creating an Account

1. Click **Login / Sign Up** in the top-right corner of the header.
2. Select the **Sign Up** tab in the modal.
3. Enter your email address and a password.
4. Click **Sign Up**.
5. You will be logged in automatically.

### 1.4 Logging In

1. Click **Login / Sign Up** in the header.
2. Enter your email and password on the **Login** tab.
3. Click **Login**.
4. Your session lasts 7 days and refreshes automatically.

> **Note:** Login is rate-limited to 5 attempts per minute for security.

### 1.5 Logging Out

Click the **Logout** button next to your email in the header bar.

---

## 2. Main Dashboard

### 2.1 Header Controls

| Control | Description |
|---------|-------------|
| **Theme Toggle** (sun/moon icon) | Switch between dark and light mode. Your preference is saved. |
| **Language Button** (English / عربي) | Switch between English and Arabic. The entire UI updates, including RTL layout for Arabic. |
| **Login / Sign Up** | Opens authentication modal (guests only). |
| **User Email + Logout** | Displayed when logged in. |

### 2.2 Global Stats Bar

Four animated metric cards appear at the top of the dashboard:

| Metric | Description |
|--------|-------------|
| **Stocks Tracked** | Total number of distinct stocks in the system |
| **Total Predictions** | Cumulative count of all AI predictions made |
| **Overall Accuracy** | System-wide prediction accuracy percentage |
| **Latest Data Date** | Most recent market data date in the system |

If the KSA evaluation pipeline has not populated fresh rows yet, these cards may show zeros or placeholders.

### 2.3 Performance Snapshot Bar

A live performance strip showing 30-day rolling metrics:

- **Win Rate** — Percentage of correct predictions
- **Alpha** — Excess return vs. TASI benchmark
- **Sharpe Ratio** — Risk-adjusted return measure
- **Max Drawdown** — Largest peak-to-trough decline

Color-coded status:
- **Green** = Healthy
- **Yellow** = Watch
- **Red** = Degraded

This strip depends on evaluated KSA `trade_recommendations` rows and benchmark data. If those rows are missing, the snapshot will render as unavailable.

### 2.4 Tab Navigation

Nine tabs organize the dashboard. Click any tab to switch views:

| Tab | Auth Required | Description |
|-----|---------------|-------------|
| Predictions | No | Live AI signals by stock |
| Briefing | No (partial) | Daily market summary |
| Trades | Yes | Today's trade recommendations |
| Portfolio | Yes | Your positions & trade history |
| Watchlist | Yes | Personalized stock tracking |
| Consensus | No | Multi-agent agreement signals |
| Performance | No | Investor-grade metrics |
| Results | No | Historical prediction accuracy |
| Prices | No | Latest market data |

### 2.5 Refresh Button

Located in the footer. Click to manually refresh all data across every tab. A toast notification confirms "Data updated successfully."

### 2.6 Disclaimer

The footer contains a legal disclaimer noting that Xmore provides informational data only and is not investment advice.

---

## 3. Predictions Tab

The default tab. Displays the latest AI predictions for all tracked stocks.

### 3.1 Predictions Table

| Column | Description |
|--------|-------------|
| **Stock** | Symbol + company name. Stocks are grouped — if multiple agents predict the same stock, the stock name appears once with a row span. |
| **Sentiment** | Color-coded badge: **Bullish** (green), **Neutral** (gray), or **Bearish** (red), sourced from Finnhub news analysis. |
| **Agent** | Name of the AI agent that made the prediction. Hover for a tooltip describing the agent's strategy. |
| **Prediction** | Signal direction: **UP**, **DOWN**, or **HOLD** |
| **Confidence** | Percentage confidence. Color-coded: green (high), yellow (medium), red (low). |
| **Target Date** | The date by which the prediction should materialize. |

### 3.2 Search

Use the search box above the table to filter by stock symbol or company name. Filtering is instant and case-insensitive.

### 3.3 AI Agents

| Agent | Strategy |
|-------|----------|
| **MA_Crossover_Agent** | Analyzes moving average crossovers to identify trend changes |
| **ML_RandomForest** | Machine learning model trained on historical price patterns |
| **RSI_Agent** | Uses the Relative Strength Index to detect overbought/oversold conditions |
| **Volume_Spike_Agent** | Detects unusual volume activity that may signal upcoming moves |

### 3.4 TradingView Ticker

A live TASI index ticker tape runs across the top of the predictions view, showing real-time market data. It automatically adapts to your selected theme (dark/light).

Operational note: on the KSA deployment, the ticker depends on `/api/ksa/ticker`. If prices are missing in the production database, the tape will appear empty or degraded.

---

## 4. Briefing Tab

A daily market intelligence summary generated after each trading day.

### 4.1 Public Sections (Available to All Users)

#### Market Pulse
- Market direction: Bullish, Bearish, or Mixed
- Market breadth: Advancing vs. declining stock counts
- Volume comparison vs. previous day
- Average confidence across all signals
- Top 3 gainers and top 3 losers

#### Sector Breakdown
- Signal distribution by sector (e.g., Banking, Real Estate, etc.)
- Sector names displayed in your selected language

#### Risk Alerts
- Summary counts: Passed / Flagged / Downgraded / Blocked
- Lists which stocks triggered risk alerts and why

#### Sentiment Snapshot
- Overall sentiment distribution across all tracked stocks
- Positive, negative, and neutral article counts
- Highlights stocks with particularly strong sentiment signals

### 4.2 Logged-in Sections (Require Login)

#### Your Actions Today
- Urgent BUY/SELL signals from your watchlist
- Includes entry zone, target price, stop loss, and conviction level
- Only stocks you follow appear here

#### Portfolio Snapshot
- Open position count and total unrealized P&L
- Best and worst performing positions
- Days held for each position

#### Watchlist Signal Map
- Your followed stocks ranked by signal strength
- Shows consensus signal and confidence for each
- Sorted by bull-bear score differential

### 4.3 No Briefing Available

If no briefing has been generated for today, a message displays: "No briefing available yet." Briefings are generated daily after market analysis completes.

On KSA, this usually means the daily pipeline has not yet written a KSA-compatible briefing row.

---

## 5. Trades Tab

**Requires login.** Displays today's actionable trade recommendations.

### 5.1 Summary Strip

At the top, a summary shows counts of each recommendation type:

| Action | Meaning |
|--------|---------|
| **BUY** | Enter a long position |
| **SELL** | Exit or short |
| **HOLD** | Maintain current position |
| **WATCH** | Monitor for potential entry |

### 5.2 Trade Cards

Each recommendation is displayed as a card containing:

| Field | Description |
|-------|-------------|
| **Stock** | Symbol + company name + sector |
| **Action Badge** | BUY (green), SELL (red), HOLD (yellow), WATCH (blue) |
| **Entry Zone** | Suggested entry price |
| **Target Price** | Price target for profit-taking |
| **Stop Loss** | Suggested stop-loss level |
| **Risk/Reward** | Ratio of potential gain to potential loss |
| **Conviction** | Very High / High / Moderate / Low / Blocked |
| **Bull vs Bear Score** | Numeric strength of bullish and bearish arguments |
| **Agent Agreement** | How many agents agree (e.g., "3 of 4 agree") |
| **Risk Action** | PASS / FLAG / DOWNGRADE / BLOCK |
| **Analysis** | Written rationale in your selected language |

### 5.3 Stale Data Notice

If no recommendations exist for today, the system falls back to the most recent available date and shows a notice: "Data from [date]".

For the KSA branch, stale data is preferable to a hard failure. An older KSA date indicates the pipeline is lagging, not necessarily that the page is broken.

### 5.4 Not Logged In

Guests see: "Login to view personalized recommendations" with a login button.

---

## 6. Portfolio Tab

**Requires login.** Track your positions and trade history.

### 6.1 Portfolio Stats

Four mini-cards at the top:

- **Open Positions** — Count of active trades
- **Unrealized P&L** — Total percentage return on open positions
- **Best Position** — Stock symbol + return %
- **Worst Position** — Stock symbol + return %

### 6.2 Open Positions Table

| Column | Description |
|--------|-------------|
| **Symbol** | Stock symbol + company name |
| **Sector** | Stock sector |
| **Entry Date** | When the position was opened |
| **Entry Price** | Purchase price |
| **Current Price** | Latest market price |
| **Return %** | Unrealized gain/loss (green = profit, red = loss) |
| **Days Held** | Duration since entry |

### 6.3 Trade History Table

A paginated table of all closed trades:

| Column | Description |
|--------|-------------|
| **Symbol** | Stock symbol + company name |
| **Entry Date & Price** | When and at what price you entered |
| **Exit Date & Price** | When and at what price you exited |
| **Return %** | Realized gain or loss |
| **Days Held** | Duration of the trade |
| **Outcome** | Correct or incorrect |

**Filters:**
- Filter by action (BUY / SELL / HOLD)
- Filter by stock symbol
- Pagination: 20 records per page (max 50)

---

## 7. Watchlist Tab

**Requires login.** Build a personal list of stocks to track (up to 30).

### 7.1 Adding Stocks

1. Click the **Add Stock** button.
2. Type a stock symbol, company name, or sector in the search box.
3. Results appear instantly — click **Follow** to add a stock.
4. The button changes to **Following** once added.

> **Limit:** Maximum 30 stocks per watchlist.

### 7.2 Watchlist Cards

Each followed stock displays as a card with:

- Stock symbol and company name (in your selected language)
- Sector
- Latest prediction + confidence from AI agents
- Consensus signal + conviction level
- Agent agreement count
- **Remove** button to unfollow

### 7.3 Empty States

- **Not logged in:** "Login to create your watchlist"
- **Empty watchlist:** "No stocks in your watchlist yet"
- **Max reached:** A message when you hit 30 stocks

---

## 8. Consensus Tab

Shows where multiple AI agents agree on a stock's direction.

### 8.1 Overview Cards

Four summary cards:

| Card | Description |
|------|-------------|
| **Total Stocks** | Number of stocks with consensus data |
| **Passed** | Stocks that cleared risk checks |
| **Flagged** | Stocks with risk warnings |
| **Blocked** | High-risk signals blocked from recommendations |

### 8.2 Consensus Cards

Each stock with consensus data shows a card:

| Field | Description |
|-------|-------------|
| **Symbol + Name** | Stock identification |
| **Final Signal** | UP / DOWN / HOLD (the combined verdict) |
| **Conviction** | Very High / High / Moderate / Low / Blocked |
| **Agent Agreement** | Fraction of agents that agree (e.g., "3 of 4") |
| **Bull vs Bear Score** | Numeric strength of each side |
| **Risk Assessment** | PASS / FLAG / BLOCK / DOWNGRADE |
| **Risk Flags** | Specific risk concerns (if any) |

### 8.3 Expanded Details

Click a consensus card to expand it and see:

- **Bull Case** — Rationale for upside
- **Bear Case** — Rationale for downside
- **Reasoning Chain** — Step-by-step logic from agents
- **Agent Signal Breakdown** — What each individual agent predicted

---

## 9. Performance Tab

An investor-grade performance dashboard. All data is from **live predictions only** (no backtested data).

### 9.1 System Health Status

A status badge at the top:

| Status | Criteria |
|--------|----------|
| **Stable** | Sharpe > 1.0, Alpha > 0%, Max Drawdown <= 8% |
| **Watch** | Sharpe > 0.6, Alpha >= 0%, Max Drawdown <= 12% |
| **Degraded** | Everything else |

Label: "Live-Only Immutable Logs" — indicating all data is real, not simulated.

### 9.2 Proof of Edge

Three headline metric cards:

| Metric | Description |
|--------|-------------|
| **Alpha** | 30-day excess return vs. TASI benchmark (%) |
| **Sharpe Ratio** | 30-day risk-adjusted return |
| **Max Drawdown** | 30-day largest peak-to-trough decline (%) |

### 9.3 Equity Curve Chart

An interactive chart (powered by TradingView Lightweight Charts) showing:

- **Xmore Strategy** (green line) — Cumulative return of AI predictions
- **TASI Benchmark** (gray line) — Market benchmark return
- **Alpha shading** — Visual difference between the two

**Controls:**
- **Period selector:** 30d / 60d / 90d / 180d
- **Show TASI benchmark:** Toggle benchmark line on/off
- **Show drawdown zones:** Highlight periods of decline

**Legend:** Shows current Xmore %, TASI %, and Alpha %.

### 9.4 Stability Metrics Table

Rolling-window metrics across three timeframes:

| Metric | 30 Days | 60 Days | 90 Days |
|--------|---------|---------|---------|
| Win Rate % | | | |
| Volatility % | | | |
| Profit Factor | | | |
| Trade Count | | | |

### 9.5 Agent Accountability Table

Per-agent performance comparison:

| Column | Description |
|--------|-------------|
| **Agent** | Agent display name |
| **30-Day Win Rate** | Accuracy over last 30 days |
| **30-Day Predictions** | Number of predictions in period |
| **90-Day Win Rate** | Accuracy over last 90 days |
| **90-Day Predictions** | Number of predictions in period |

Sorted by 30-day win rate (best first).

### 9.6 Transparency Log

A paginated table of every live prediction and its outcome:

| Column | Description |
|--------|-------------|
| **Date** | When the prediction was made |
| **Stock** | Symbol |
| **Signal** | UP / DOWN / HOLD |
| **Confidence** | Percentage |
| **Correct** | Checkmark or X |
| **1-Day Return** | Actual price change % |
| **Outcome** | Correct / Incorrect |

Pagination: 10 records per page.

### 9.7 Since Inception

Global all-time statistics:

- Total Alpha %
- Overall Sharpe Ratio
- Total Prediction Count
- First Live Date

---

## 10. Results Tab

Historical record of prediction evaluations.

### 10.1 Results Table

| Column | Description |
|--------|-------------|
| **Stock** | Symbol |
| **Agent** | Which AI agent made the prediction |
| **Prediction** | What was predicted (UP / DOWN / HOLD) |
| **Actual** | What actually happened |
| **Correct** | Checkmark or X |
| **Price Change %** | 1-day actual price movement |
| **Prediction Date** | When the prediction was made |
| **Target Date** | The evaluation date |

Results are grouped by stock and sorted by target date (most recent first). Limited to the last 100 evaluations.

---

## 11. Prices Tab

Latest market data for all tracked stocks.

### 11.1 Prices Table

| Column | Description |
|--------|-------------|
| **Symbol** | Stock ticker |
| **Company** | Full company name |
| **Close** | Latest closing price |
| **Volume** | Trading volume (formatted with commas) |
| **Date** | Date of the price data |

---

## 12. Mobile & Responsive Design

The Xmore dashboard is fully responsive and optimized for all device sizes, from mobile phones (640px) to desktop displays.

### 12.1 Mobile Devices (640px and below)

On small screens, the UI intelligently adapts to prevent overlapping elements and maintain readability:

#### Header
- Navigation links are hidden to save space (only PRO, Language, and Theme buttons visible)
- Logo font size reduces from 24px to 18px
- Buttons are properly stacked with adequate spacing (36px minimum height for touch targets)
- No horizontal overflow or content cramping

#### Content Layout
- Stats grid converts to 2-column layout instead of 4-column
- Charts and tables enable horizontal scroll with sticky headers
- Card padding is optimized: 10px instead of 16px
- Font sizes scale appropriately (labels 0.75em, values 1.6em)

#### Tables & Data
- Minimum widths (380-560px) allow horizontal scroll without breaking layout
- Reduced padding (8px per cell) maintains readability
- Columns don't resize or collapse unexpectedly

#### Navigation Tabs
- Horizontal scroll with touch-friendly scrolling
- Smaller gap spacing (4px) to fit more tabs on screen
- Tab font size: 0.75em for compact display

#### Buttons & Touch Targets
- All buttons maintain 36px minimum height for easy mobile tapping
- Consistent padding: 8px × 12px
- No overlapping or cramped spacing

#### Text Rendering
- All text uses `word-break: break-word` to prevent overflow
- Proper line-height (1.2-1.4) for readability
- Long text gracefully wraps instead of being clipped

### 12.2 Tablet Devices (768px)

- Stats grid: 2-column layout
- Reduced padding (12px) maintains spacious feel
- Full navigation visible
- Charts and tables remain readable without zoom

### 12.3 Desktop (1024px+)

- Full 4-column stats grid
- All navigation and secondary links visible
- Optimal spacing and font sizes
- Best visual performance

### 12.4 Dark Mode & Mobile

Dark mode works seamlessly on all device sizes:
- Proper contrast ratios maintained on small screens
- No additional styling issues or visual glitches
- Toggle via the moon/sun icon in the header

### 12.5 RTL (Arabic) & Mobile

Arabic language support is fully mobile-optimized:
- Text alignment automatically switches to right-aligned on RTL mode
- Tables and lists display correctly with proper text direction
- Touch targets and buttons remain properly positioned

### 12.6 Performance on Mobile

- No page bloat or excessive rendering
- Smooth scrolling using GPU acceleration (`-webkit-overflow-scrolling: touch`)
- Reduced animations to prevent jank on lower-end devices
- Proper viewport meta tag ensures correct scaling

---

## 13. Account & Settings

(Previous section content continues...)

Sorted alphabetically by symbol.

---

## 12. Account & Settings

### 12.1 Profile Updates

Logged-in users can update:

- **Display Name** — How your name appears in the system
- **Preferred Language** — English or Arabic (synced with the UI toggle)

### 12.2 Session Details

- Sessions last **7 days** via secure httpOnly cookies.
- Tokens auto-refresh when fewer than 3 days remain.
- Passwords are hashed with bcrypt (12 rounds).

### 12.3 Theme Preference

Click the sun/moon icon in the header. Your choice is saved in the browser and persists across sessions. If no preference is set, the system detects your OS preference (dark/light mode).

### 12.4 Language Preference

Click the language button in the header to toggle between **English** and **Arabic**. When Arabic is selected:

- All text switches to Arabic translations
- Layout changes to right-to-left (RTL)
- Preference is saved in localStorage and your user profile

---

## 13. Admin Dashboard

Accessible at `/admin`. Requires the `ADMIN_SECRET` environment variable.

### 13.1 Entering the Admin Secret

1. Navigate to `/admin`.
2. Enter the admin secret in the password field at the top.
3. Click **Save**. The secret is stored in your browser.
4. Status shows "Secret saved in browser storage."

All admin API calls include this secret in the request header. If the secret is incorrect, requests return 403 Forbidden.

### 13.2 System Health

Two side-by-side cards:

#### Latest Audit Log
- **Table** — Which database table was modified
- **Field** — Which field changed
- **Timestamp** — When the change occurred

Shows "No audit data available" if no audit entries exist.

#### Latest Agent Daily Snapshot
- **Date** — Snapshot date
- **Agent** — Agent name
- **30-Day Stats** — Win rate % and prediction count
- **90-Day Stats** — Win rate % and prediction count

Shows "No agent daily data available" if no snapshots exist.

### 13.3 Knowledge Base Upload

Upload market research PDFs or images for text extraction and archival.

#### How to Upload
1. **Drag and drop** a file onto the upload zone, **or** click the zone to browse files.
2. Wait for processing to complete.
3. A success message shows: "Processed: filename.pdf (EN)" with the detected language.

#### Supported File Types

| Type | Extensions | Processing |
|------|-----------|------------|
| PDF | `.pdf` | Text extraction via pdf-parse |
| Images | `.png`, `.jpg`, `.jpeg`, `.webp`, `.bmp`, `.tiff`, `.tif` | OCR via Tesseract.js (English + Arabic) |

**Maximum file size:** 25 MB

#### Processing Details
- **Language Detection:** Automatic. Counts Arabic vs. Latin characters to determine EN or AR.
- **Summary Generation:** The system extracts the most actionable sentences — those containing stock signals (buy, sell, bullish, bearish, target, upgrade, etc.). If no signal sentences are found, it uses the concluding sentences.

### 13.4 Report List

A table of all uploaded reports:

| Column | Description |
|--------|-------------|
| **Filename** | Original uploaded file name |
| **Upload Date** | When the file was uploaded |
| **Language** | Detected language (EN or AR) |
| **Status** | Processed (text extracted) or Pending |
| **Summary** | Extracted actionable summary |

---

## 14. Bilingual Support

The entire system supports **English** and **Arabic**.

### What Gets Translated
- All tab names and section headers
- Button labels and input placeholders
- Table column headers
- Error messages and empty-state messages
- Agent names and descriptions
- Sentiment labels (Bullish/Neutral/Bearish)
- Performance metric labels
- Conviction levels and risk action labels
- Trade analysis/reasoning text
- Briefing content
- Stock company names and sector names
- Footer disclaimer text

### How It Works
- Click the language toggle in the header (English / عربي)
- The UI instantly switches language and layout direction
- Arabic activates right-to-left (RTL) layout
- Preference is saved in `localStorage` and your user account

---

## 15. Keyboard & Accessibility

### Keyboard Navigation
- **Tab** key navigates between interactive elements
- **Enter/Space** activates buttons and tab switches
- The upload drop zone is keyboard-accessible

### Screen Readers
- Semantic HTML with proper ARIA attributes (`aria-label`, `aria-selected`, `role="tablist"`)
- Skip-to-content link at the top of the page

### Touch Devices
- All touch targets are 44px or larger
- Hover-dependent features have touch alternatives

### Print
- Use your browser's print function (Ctrl+P / Cmd+P)
- Navigation, buttons, and interactive elements are hidden in print
- Tables and data render cleanly on paper

### Responsive Breakpoints

| Width | Layout |
|-------|--------|
| > 1024px | Full desktop layout |
| 768–1024px | Tablet layout, condensed grids |
| 480–768px | Mobile layout, single column |
| < 480px | Compact mobile, stacked elements |

---

## Appendix: API Endpoints Reference

### Public Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/predictions` | Latest AI predictions |
| GET | `/api/prices` | Latest market prices |
| GET | `/api/sentiment` | Sentiment scores per stock |
| GET | `/api/stats` | System statistics |
| GET | `/api/evaluations` | Prediction evaluation results |
| GET | `/api/consensus` | All consensus signals |
| GET | `/api/consensus/:symbol` | Detailed consensus for one stock |
| GET | `/api/stocks` | All TASI stocks (for search) |
| GET | `/api/risk/overview` | Portfolio-level risk assessment |
| GET | `/api/performance-v2/summary` | Overall performance metrics |
| GET | `/api/performance-v2/by-agent` | Per-agent performance |
| GET | `/api/performance-v2/equity-curve` | Equity curve data (query: `days`) |
| GET | `/api/performance-v2/predictions/history` | Prediction log (query: `page`, `limit`) |

### Authenticated Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/auth/signup` | Register new account |
| POST | `/api/auth/login` | Login (rate-limited) |
| POST | `/api/auth/logout` | Logout |
| GET | `/api/auth/me` | Get current user session |
| PUT | `/api/auth/me` | Update profile |
| GET | `/api/watchlist` | Get user's watchlist |
| POST | `/api/watchlist/:stockId` | Add stock to watchlist |
| DELETE | `/api/watchlist/:stockId` | Remove stock from watchlist |
| GET | `/api/trades/today` | Today's trade recommendations |
| GET | `/api/trades/history` | Trade history (query: `page`, `limit`, `action`, `symbol`) |
| GET | `/api/trades/portfolio` | User's open & closed positions |
| GET | `/api/briefing/today` | Daily briefing (personalized if logged in) |

### Admin Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/admin/system-health` | Audit log + agent daily snapshot |
| GET | `/api/admin/reports` | List uploaded reports |
| POST | `/api/admin/reports/upload` | Upload PDF or image report |

> All admin endpoints require the `x-admin-secret` header matching the `ADMIN_SECRET` environment variable.
