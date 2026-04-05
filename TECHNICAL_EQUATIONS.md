# Xmore — Technical Equations & Workflow Reference

> **Scope**: Every quantitative formula, signal rule, and decision boundary used in the Xmore signal pipeline, ML engine, risk layer, and execution model. Source-mapped to the actual implementation file.

---

## Table of Contents

1. [Pipeline Overview](#0-pipeline-overview)
2. [Feature Engineering](#1-feature-engineering)
   - 1.1 Trend Indicators
   - 1.2 Momentum Indicators
   - 1.3 Volatility Indicators
   - 1.4 Volume Indicators
   - 1.5 GARCH-Inspired Volatility Features
   - 1.6 Macro Features
3. [Signal Agents](#2-signal-agents)
   - 2.1 RSI Agent
   - 2.2 Moving Average Crossover Agent
   - 2.3 Volume Spike Agent
   - 2.4 ML / LightGBM Agent
4. [Bull / Bear Evaluator](#3-bull--bear-evaluator)
5. [Consensus Engine](#4-consensus-engine)
6. [Risk Agent](#5-risk-agent)
7. [Execution Model](#6-execution-model)
   - 6.1 EGX Transaction Cost Structure
   - 6.2 Slippage Model
   - 6.3 Position Sizing
   - 6.4 Fill Ratio Model
8. [Backtest Harness](#7-backtest-harness)
9. [Prediction Evaluation](#8-prediction-evaluation)
10. [Circuit Breaker](#9-circuit-breaker)

---

## 0. Pipeline Overview

```
collect_data.py
     │  prices + news + macro
     ▼
features.py
     │  40+ technical indicators
     ▼
┌─────────────────────────────────────┐
│  RSI Agent │ MA Agent │ Vol Agent   │
│         ML / LightGBM Agent         │
└─────────────────────────────────────┘
     │  agent_signals (UP/DOWN/HOLD + confidence)
     ▼
bull_bear_evaluator.py  ──►  bull_score, bear_score
     │
     ▼
consensus_engine.py  ──►  weighted_vote → final_signal
     │
     ▼
risk_agent.py  ──►  PASS / FLAG / DOWNGRADE / BLOCK
     │
     ▼
execution_config.py  ──►  position_size, slippage, fill_ratio
     │
     ▼
database  ──►  predictions table
     │
     ▼
evaluate.py  ──►  evaluations table (was_correct, accuracy)
```

**Prediction horizon**: 5 trading days  
**Universe**: EGX-30 (.CA suffix) + select US symbols  
**Operating hours**: Sun–Thu 07:00–12:00 UTC (EGX session)

---

## 1. Feature Engineering

> Source: [`features.py`](features.py)

### 1.1 Trend Indicators

**Simple Moving Average (SMA)**

$$\text{SMA}_n(t) = \frac{1}{n} \sum_{i=0}^{n-1} C_{t-i}$$

Computed for $n \in \{10, 30, 50\}$ where $C_t$ = close price at time $t$.

---

**Exponential Moving Average (EMA)**

$$\text{EMA}_n(t) = C_t \cdot \alpha + \text{EMA}_n(t-1) \cdot (1 - \alpha), \quad \alpha = \frac{2}{n+1}$$

Computed for $n \in \{12, 26\}$.

---

**MACD (Moving Average Convergence Divergence)**

$$\text{MACD}(t) = \text{EMA}_{12}(t) - \text{EMA}_{26}(t)$$

$$\text{Signal Line}(t) = \text{EMA}_9(\text{MACD})(t)$$

$$\text{MACD Histogram}(t) = \text{MACD}(t) - \text{Signal Line}(t)$$

---

**ADX / Directional Movement Index**

True Range:
$$\text{TR}(t) = \max\!\left(H_t - L_t,\; |H_t - C_{t-1}|,\; |L_t - C_{t-1}|\right)$$

Directional Movement:
$$+\text{DM}(t) = \max(H_t - H_{t-1},\; 0) \quad \text{if } H_t - H_{t-1} > L_{t-1} - L_t$$
$$-\text{DM}(t) = \max(L_{t-1} - L_t,\; 0) \quad \text{if } L_{t-1} - L_t > H_t - H_{t-1}$$

Directional Indices (Wilder-smoothed over $n=14$):
$$+\text{DI}_{14} = \frac{\widetilde{+\text{DM}}_{14}}{\widetilde{\text{TR}}_{14}} \times 100, \qquad -\text{DI}_{14} = \frac{\widetilde{-\text{DM}}_{14}}{\widetilde{\text{TR}}_{14}} \times 100$$

$$\text{ADX}_{14} = \text{EMA}_{14}\!\left(\frac{|{+\text{DI}} - {-\text{DI}}|}{+\text{DI} + -\text{DI}} \times 100\right)$$

---

### 1.2 Momentum Indicators

**RSI (Relative Strength Index)**

Using Wilder's exponential smoothing ($\alpha = 1/n$, no adjust):

$$\overline{G}_n = \text{EWM}_\alpha(\max(\Delta C, 0)), \qquad \overline{L}_n = \text{EWM}_\alpha(\max(-\Delta C, 0))$$

$$\text{RS}(t) = \frac{\overline{G}_n(t)}{\overline{L}_n(t)}, \qquad \text{RSI}(t) = 100 - \frac{100}{1 + \text{RS}(t)}$$

Default period $n = 14$. Regime-adjusted: $n_{\text{low}} = 10$, $n_{\text{normal}} = 14$, $n_{\text{high}} = 20$.

---

**Stochastic Oscillator**

$$\%K(t) = \frac{C_t - \min_{14}(L)}{\max_{14}(H) - \min_{14}(L)} \times 100$$

$$\%D(t) = \text{SMA}_3(\%K)(t)$$

---

**Williams %R**

$$\%R(t) = \frac{\max_{14}(H) - C_t}{\max_{14}(H) - \min_{14}(L)} \times (-100)$$

---

**CCI (Commodity Channel Index)**

Typical Price:
$$\text{TP}(t) = \frac{H_t + L_t + C_t}{3}$$

Mean Absolute Deviation:
$$\text{MAD}_{20}(t) = \frac{1}{20} \sum_{i=0}^{19} \left|\text{TP}_{t-i} - \overline{\text{TP}}_{20}(t)\right|$$

$$\text{CCI}_{20}(t) = \frac{\text{TP}(t) - \overline{\text{TP}}_{20}(t)}{0.015 \cdot \text{MAD}_{20}(t)}$$

---

**MFI (Money Flow Index)** — volume-weighted RSI

$$\text{MF}(t)= \text{TP}(t) \times V_t$$

Positive/Negative flows summed over 14 periods, then:

$$\text{MFI}_{14}(t) = 100 - \frac{100}{1 + \frac{\sum \text{MF}^+_{14}}{\sum \text{MF}^-_{14}}}$$

---

**ROC (Rate of Change)**

$$\text{ROC}_{10}(t) = \frac{C_t - C_{t-10}}{C_{t-10}} \times 100$$

---

### 1.3 Volatility Indicators

**Bollinger Bands**

$$\text{BB\_Middle}_{20}(t) = \overline{C}_{20}(t)$$

$$\text{BB\_Upper}(t) = \overline{C}_{20}(t) + 2\,\sigma_{20}(t)$$

$$\text{BB\_Lower}(t) = \overline{C}_{20}(t) - 2\,\sigma_{20}(t)$$

---

**ATR (Average True Range)**

$$\text{ATR}_{14}(t) = \frac{1}{14} \sum_{i=0}^{13} \text{TR}_{t-i}$$

**NATR (Normalised ATR)**

$$\text{NATR}_{14}(t) = \frac{\text{ATR}_{14}(t)}{C_t} \times 100$$

---

**Daily Returns and Rolling Volatility**

$$r_t = \frac{C_t - C_{t-1}}{C_{t-1}}$$

$$\sigma_{20}^{\text{roll}}(t) = \sqrt{\frac{1}{20} \sum_{i=0}^{19} (r_{t-i} - \bar{r})^2}$$

---

### 1.4 Volume Indicators

**OBV (On Balance Volume)**

$$\text{OBV}(t) = \text{OBV}(t-1) + \begin{cases} +V_t & C_t > C_{t-1} \\ -V_t & C_t < C_{t-1} \\ 0 & C_t = C_{t-1} \end{cases}$$

---

**A/D Line (Accumulation / Distribution)**

$$\text{CLV}(t) = \frac{(C_t - L_t) - (H_t - C_t)}{H_t - L_t}$$

$$\text{AD}(t) = \text{AD}(t-1) + \text{CLV}(t) \times V_t$$

---

### 1.5 GARCH-Inspired Volatility Features

> Source: [`features.py` → `_add_garch_inspired_features()`](features.py)

Three features that approximate GARCH(1,1) dynamics without requiring the `arch` library:

**EWMA Volatility** (RiskMetrics standard, $\lambda \approx 0.94 \Leftrightarrow \text{span}=32$)

$$\hat{\sigma}_t^{\text{EWMA}} = \sqrt{(1-\lambda)\,r_t^2 + \lambda\,(\hat{\sigma}_{t-1}^{\text{EWMA}})^2}$$

Implemented as:
$$\hat{\sigma}_t^{\text{EWMA}} = \text{EWM}_{\text{span}=32}(\,|r_t|\,)_{\text{std}}$$

---

**Volatility of Volatility** (vol-of-vol, 10-day window)

$$\sigma^{\text{vov}}_{10}(t) = \text{std}_{10}\!\left(\hat{\sigma}_{t}^{\text{EWMA}}\right)$$

High $\sigma^{\text{vov}}$ → uncertainty about uncertainty (regime transition signal).

---

**Volatility Persistence** (lag-1 autocorrelation of squared returns, 20-day window)

$$\rho_1(t) = \text{Corr}\!\left(r_{t-1}^2,\; r_t^2\right)_{\text{rolling-20}}$$

$\rho_1 > 0$ → volatility clustering (GARCH-like); $\rho_1 \approx 0$ → mean-reverting.

---

### 1.6 Macro Features

> Source: [`features.py` → `add_macro_features()`](features.py)

Three macro signals are merged onto the price DataFrame as 5-day rolling returns:

$$r_t^{\text{Brent},5} = \frac{P_t^{\text{Brent}} - P_{t-5}^{\text{Brent}}}{P_{t-5}^{\text{Brent}}}$$

$$r_t^{\text{USD/EGP},5} = \frac{P_t^{\text{USD/EGP}} - P_{t-5}^{\text{USD/EGP}}}{P_{t-5}^{\text{USD/EGP}}}$$

$$r_t^{\text{EEM},5} = \frac{P_t^{\text{EEM}} - P_{t-5}^{\text{EEM}}}{P_{t-5}^{\text{EEM}}}$$

Missing series are filled with $0$ (neutral signal).

---

## 2. Signal Agents

### 2.1 RSI Agent

> Source: [`agents/agent_rsi.py`](agents/agent_rsi.py)

**Volatility Regime Classification**

$$\hat{\sigma}^{\text{EWMA}}_t = \text{EWM}_{\text{span}=32}(r_t)_{\text{std}}$$

| Regime | Condition | RSI Period |
|--------|-----------|-----------|
| Low | $\hat{\sigma} < 1.5\%$ | $n = 10$ |
| Normal | $1.5\% \le \hat{\sigma} \le 3.0\%$ | $n = 14$ |
| High | $\hat{\sigma} > 3.0\%$ | $n = 20$ |

**Signal Rules**

$$\text{Signal} = \begin{cases} \text{UP} & \text{RSI}_n < 30 \text{ (oversold)} \\ \text{DOWN} & \text{RSI}_n > 70 \text{ (overbought)} \\ \text{HOLD} & 30 \le \text{RSI}_n \le 70 \end{cases}$$

Sentiment confirmation: bullish sentiment boosts UP confidence; bearish sentiment boosts DOWN confidence.

---

### 2.2 Moving Average Crossover Agent

> Source: [`agents/agent_ma.py`](agents/agent_ma.py)

**Regime-Adjusted Windows**

| Regime | Short Window | Long Window |
|--------|-------------|------------|
| Low volatility | 8 | 20 |
| Normal | 10 | 30 |
| High volatility | 15 | 40 |

**Golden Cross / Death Cross**

$$\text{Signal} = \begin{cases} \text{UP} & \text{SMA}_{\text{short}}(t) > \text{SMA}_{\text{long}}(t) \text{ (Golden Cross)} \\ \text{DOWN} & \text{SMA}_{\text{short}}(t) < \text{SMA}_{\text{long}}(t) \text{ (Death Cross)} \\ \text{HOLD} & \text{insufficient data} \end{cases}$$

---

### 2.3 Volume Spike Agent

> Source: [`agents/agent_volume.py`](agents/agent_volume.py)

**Volume Spike Detection**

$$\bar{V}_{20}(t) = \frac{1}{20} \sum_{i=1}^{20} V_{t-i} \quad \text{(lagged 1 day to avoid look-ahead)}$$

$$\text{Spike}(t) = V_t > 1.5 \times \bar{V}_{20}(t)$$

**Volume Ratio**

$$\rho_V(t) = \frac{V_t}{\bar{V}_{20}(t)}$$

**Signal Logic**

$$\text{Signal} = \begin{cases} \text{UP} & \text{Spike}(t) = \text{True} \wedge C_t > C_{t-1} \\ \text{DOWN} & \text{Spike}(t) = \text{True} \wedge C_t < C_{t-1} \\ \text{HOLD} & \text{otherwise} \end{cases}$$

**Confidence Scoring**

| Condition | Confidence Δ |
|-----------|-------------|
| Base | +40 |
| $\rho_V > 2.0$ (extreme spike) | +25 |
| $\rho_V > 1.5$ (standard spike) | +8 |
| ≥2 consecutive high-vol days | +5 |
| Directional prediction | +7 |
| $\rho_V < 0.7$ (thin volume) | −15 |

Final confidence clipped: $\text{confidence} \in [15, 90]$.

---

### 2.4 ML / LightGBM Agent

> Source: [`agents/agent_ml.py`](agents/agent_ml.py)

**Target Variable** (5-day forward return)

$$y_t = \frac{C_{t+5} - C_t}{C_t}$$

$$\hat{y}_t^{\text{label}} = \begin{cases} \text{UP} & y_t \ge +0.5\% \\ \text{DOWN} & y_t \le -0.5\% \\ \text{FLAT} & -0.5\% < y_t < +0.5\% \end{cases}$$

**Model Architecture**

LightGBM Gradient Boosted Trees:

$$\hat{F}(x) = \sum_{m=1}^{M} \gamma_m h_m(x), \quad M = 300 \text{ trees}$$

Objective: multi-class cross-entropy with `class_weight='balanced'`.

Hyperparameters (Optuna-tuned, 25 TPE trials per symbol):
- `max_depth = 6`, `num_leaves = 31`, `learning_rate = 0.05`
- `subsample = 0.8`, `colsample_bytree = 0.8`

**Feature Selection** (post-training)

Top-20 features by total gain importance:

$$\text{Gain}_j = \sum_{m=1}^{M} \sum_{s \in \text{splits of tree}_m} \Delta L_s \cdot \mathbf{1}[j \text{ used at split } s]$$

**Confidence Gating**

$$\text{Signal emitted only if } \max_k P(\hat{y}=k \mid x) \ge 0.60$$

Below threshold → output HOLD regardless of argmax.

**Walk-Forward Validation (TimeSeriesSplit)**

- Minimum training rows: 60
- Test fold size: 10 rows (~2 weeks)
- Default splits: 8
- Model retrained if saved file age > 7 days

---

## 3. Bull / Bear Evaluator

> Source: [`agents/bull_bear_evaluator.py`](agents/bull_bear_evaluator.py)

Two independent scoring functions each producing a score in $[0, 100]$.

**Agent Agreement Factor** (contributes up to 25 pts to bull_score)

$$\text{agreement\_ratio} = \frac{|\{a : \text{signal}_a = \text{majority\_direction}\}|}{N_{\text{agents}}}$$

| Agreement | Points |
|-----------|--------|
| 100% (unanimous) | 25 |
| ≥75% | 18 |
| ≥50% | 10 |
| <50% | 3 |

**Confidence Factor** (up to 20 pts): average confidence of agreeing agents, scaled.

**Sentiment Factor** (up to 20 pts): based on normalized sentiment score.

**Momentum Factor** (up to 20 pts): RSI/MACD cross-referenced against signal direction.

**Risk/Drawdown Factor** (up to 15 pts): recent 5-day and 20-day price drawdown.

**Final Scores**

$$\text{bull\_score}, \text{bear\_score} \in [0, 100]$$

Used downstream by the Risk Agent and presented in the UI as a confidence gauge.

---

## 4. Consensus Engine

> Source: [`agents/consensus_engine.py`](agents/consensus_engine.py), [`agents/agent_consensus.py`](agents/agent_consensus.py), and [`engines/agent_weights.py`](engines/agent_weights.py)

### 4.1 Softmax Dynamic Weighting (Primary)

> Source: [`engines/agent_weights.py`](engines/agent_weights.py)

Each agent $a$ has a 30-day rolling directional accuracy:

$$\text{acc}_a = \frac{\text{correct}_a}{\text{total}_a}$$

**Softmax with temperature** ($T = 2.0$):

$$w_a^{\text{raw}} = \frac{\exp(\text{acc}_a / T)}{\sum_j \exp(\text{acc}_j / T)}$$

**Floor enforcement** ($w_{\min} = 0.05$):

$$w_a = \max(w_a^{\text{raw}},\; w_{\min}), \qquad w_a \leftarrow \frac{w_a}{\sum_j w_j}$$

Weight history logged to `agent_weights_log` table. Falls back to equal weights when insufficient evaluation data exists.

### 4.2 Legacy Accuracy-Weighted Voting (Fallback)

Each agent $a$ has a historical accuracy weight:

$$w_a = \max\!\left(\frac{\text{correct}_a}{\text{total}_a},\; 0.1\right)$$

The 0.1 floor prevents any agent from being zeroed out. Equal weight $w_a = 0.5$ used when no evaluation history exists.

### 4.3 Vote Aggregation

$$S_{\text{UP}} = \sum_{a:\,\text{signal}_a=\text{UP}} w_a, \quad S_{\text{DOWN}} = \sum_{a:\,\text{signal}_a=\text{DOWN}} w_a, \quad S_{\text{HOLD}} = \sum_{a:\,\text{signal}_a=\text{HOLD}} w_a$$

$$\text{Consensus} = \arg\max(S_{\text{UP}},\; S_{\text{DOWN}},\; S_{\text{HOLD}})$$

**Confidence (Agreement Ratio)**

$$\text{confidence}_{\text{consensus}} = \frac{|\{a : \text{signal}_a = \text{Consensus}\}|}{N_{\text{agents}}}$$

### 4.4 Regime Signal Modifiers

> Source: [`run_agents.py` → `REGIME_SIGNAL_MODIFIERS`](run_agents.py)

Before consensus, agent signals are modified based on the current market regime from `get_current_regime()`:

| Regime | Bias | Effect |
|--------|------|--------|
| Bull | +5% UP confidence | UP threshold lowered to 55% |
| Bear | +5% DOWN confidence | DOWN threshold lowered to 55% |
| High Vol | −10% all confidence | Directional thresholds raised to 70% |
| Unknown | No bias | Default thresholds |

---

## 5. Risk Agent

> Source: [`agents/risk_agent.py`](agents/risk_agent.py)

**Liquidity Check**

$$\text{BLOCK if} \quad \bar{V}_{20} < 50{,}000 \text{ shares} \quad \text{or} \quad \text{bid-ask spread} > 3.0\%$$

**Volatility Check**

$$\text{BLOCK if} \quad \sigma_{20}^{\text{roll}} > 6\%/\text{day}$$

**Drawdown Checks**

$$\text{BLOCK if} \quad \frac{C_t - C_{t-5}}{C_{t-5}} < -15\% \quad \text{or} \quad \frac{C_t - C_{t-20}}{C_{t-20}} < -25\%$$

**Sector Concentration**

$$\text{FLAG if} \quad \frac{|\text{signals in sector}|}{|\text{total signals}|} > 40\%$$

**Signal Quality Gates**

| Check | Threshold | Action |
|-------|-----------|--------|
| Bull/Bear gap | `bull_score - bear_score < 10` | FLAG |
| Agent agreement | `< 50%` | DOWNGRADE |
| Bear score | `> 75` | BLOCK |

**Output**: one of `PASS / FLAG / DOWNGRADE / BLOCK`.

---

## 6. Execution Model

> Source: [`config/execution_config.py`](config/execution_config.py)

### 6.1 EGX Transaction Cost Structure

| Component | Rate | Direction |
|-----------|------|-----------|
| Brokerage | 0.150% | Per leg |
| Stamp Duty | 0.150% | Per leg |
| FRA fee | 0.0125% | Per leg |
| EGX fee | 0.0125% | Per leg |
| Misr Clearing | 0.010% | Per leg |
| **One-way total** | **~0.335%** | |
| **Round-trip total** | **~0.725%** | |

$$\text{EGX\_ROUND\_TRIP\_RATE} = 2 \times (0.00150 + 0.00150 + 0.000125 + 0.000125 + 0.00010) \approx 0.725\%$$

Minimum ticket: EGP 15 per order.

**Minimum Edge Rule**

Signal must have expected return $\ge 3\times$ round-trip cost:

$$\text{Expected Return} \ge 3 \times 0.725\% = 2.175\%$$

---

### 6.2 Slippage Model

Slippage assigned by ADV (Average Daily Value) tier:

| Liquidity Tier | Min ADV (EGP) | Slippage |
|---------------|--------------|---------|
| High | ≥ 5,000,000 | 10 bps = 0.10% |
| Medium | ≥ 1,000,000 | 25 bps = 0.25% |
| Low | < 1,000,000 | 60 bps = 0.60% |

**Net Directional Return**

$$r_t^{\text{gross}} = \frac{C_{\text{exit}} - C_{\text{entry}}}{C_{\text{entry}}} \times 100 \quad \text{(for UP)}$$

$$r_t^{\text{slipped}} = \frac{C_{\text{exit}}^{\text{fill}} - C_{\text{entry}}^{\text{fill}}}{C_{\text{entry}}^{\text{fill}}} \times 100$$

$$r_t^{\text{net}} = r_t^{\text{slipped}} \times \rho_{\text{fill}} - \text{txn\_cost\%}$$

where $\rho_{\text{fill}}$ is the partial fill ratio (see §6.4).

---

### 6.3 Position Sizing

> Kelly-inspired, volatility-adjusted

**Volatility adjustment factor**

$$\text{vol\_adj} = \min\!\left(\frac{\sigma_{\text{base}}}{\sigma_t},\; 2.0\right), \qquad \sigma_{\text{base}} = 2.0\%\text{/day}$$

**Conviction multiplier**

$$m_{\text{conviction}} = \begin{cases} 1.0 & \text{score} \ge 100 \\ \dfrac{\text{score} - 40}{60} & 40 \le \text{score} < 100 \\ 0.1 & \text{score} < 40 \end{cases}$$

**Volatility-implied stop**

$$\text{stop\%} = \max(2\,\sigma_t,\; 2\%)$$

**Position size** (as fraction of portfolio)

$$f = \min\!\left(\frac{\text{max\_loss\_per\_trade}}{\text{stop\%}} \times \text{vol\_adj} \times m_{\text{conviction}},\; 10\%\right)$$

Default `max_loss_per_trade = 1.5%`, hard cap = 10% per stock, 35% per sector.

---

### 6.4 Fill Ratio Model

Order size measured as fraction of Average Daily Volume (ADV):

$$\text{order\_pct\_ADV} = \frac{\text{shares\_requested}}{\text{ADV}}$$

| Order ADV % | Fill Ratio | Wait (days) |
|-------------|-----------|------------|
| ≤ 1% | 95% | 1 |
| 1–5% | 75% | 2 |
| 5–10% | 50% | 3 |
| > 10% | 30% | 5 |

Orders > 3% ADV are split across sessions.

---

## 7. Backtest Harness

> Source: [`engines/backtest.py`](engines/backtest.py)

**Walk-Forward Expanding Window**

Implemented using `sklearn.model_selection.TimeSeriesSplit`:

$$\text{Train}_k = [t_0, \; t_0 + 60 + k \times 10), \quad \text{Test}_k = [t_0 + 60 + k \times 10, \; t_0 + 60 + (k+1)\times 10)$$

for $k = 0, 1, \ldots, K-1$ ($K = 8$ by default).

**Accuracy Metrics**

$$\text{Accuracy} = \frac{|\hat{y}_t = y_t|}{N}$$

$$\text{Directional Accuracy} = \frac{|\hat{y}_t = y_t,\; \hat{y}_t \ne \text{FLAT}|}{|\hat{y}_t \ne \text{FLAT}|}$$

**Signal P&L**

$$\text{PnL}_t = \begin{cases} +|r_t| & \hat{y}_t = \text{UP} \wedge y_t = \text{UP} \\ +|r_t| & \hat{y}_t = \text{DOWN} \wedge y_t = \text{DOWN} \\ -|r_t| & \hat{y}_t \ne \text{FLAT} \wedge \hat{y}_t \ne y_t \\ 0 & \hat{y}_t = \text{FLAT} \end{cases}$$

**Cost-adjusted P&L**

$$\text{Net PnL}_t = \text{PnL}_t - \text{EGX\_ROUND\_TRIP\_RATE} \times 100$$

where EGX round-trip rate = 0.725%.

---

## 8. Prediction Evaluation

> Source: [`evaluate.py`](evaluate.py)

**Outcome Classification** (5-day forward return)

$$\Delta_t = \frac{C_{\text{target}} - C_{\text{prediction\_date}}}{C_{\text{prediction\_date}}}$$

$$\text{Actual Outcome} = \begin{cases} \text{UP} & \Delta_t \ge +0.5\% \\ \text{DOWN} & \Delta_t \le -0.5\% \\ \text{FLAT} & |\Delta_t| < 0.5\% \end{cases}$$

**Correctness**

$$\text{was\_correct} = \begin{cases} 1 & \hat{y} = \text{Actual Outcome} \\ 0 & \text{otherwise} \end{cases}$$

**Agent Accuracy** (feeds back into consensus weights)

$$\text{accuracy}_a = \frac{\sum_t \text{was\_correct}_{a,t}}{N_{a,t}}$$

---

### 8.1 Calibrated Evaluation Metrics

> Source: [`evaluate.py` → `evaluate_prediction()`](evaluate.py)

**Direction Sign**

$$d_t = \begin{cases} +1 & \hat{y}_t = \text{Actual Outcome}_t \\ -1 & \text{otherwise} \end{cases}$$

**Magnitude Score** (rewards size of correct calls)

$$M_t = d_t \times \min\!\left(\frac{|\Delta_t|}{5.0},\; 1.0\right)$$

Range: $[-1, +1]$. Correct UP call with 3% return → $+0.6$. Wrong call with 3% return → $-0.6$.

**Brier Calibration Score**

$$B_t = 1 - (\hat{p}_t - o_t)^2$$

where $\hat{p}_t$ = predicted confidence (0–1) and $o_t = \mathbf{1}[\text{was\_correct}]$. Perfect calibration → $B = 1$.

**Signal Strength** (for IC computation)

$$\text{SS}_t = \hat{p}_t \times d_t$$

Range: $[-1, +1]$. High positive = confident correct; high negative = confident wrong.

### 8.2 Information Coefficient (IC)

> Source: [`engines/evaluate_performance.py` → `compute_information_coefficient()`](engines/evaluate_performance.py)

$$\text{IC} = \rho_S(\text{SS}_{1:N},\; \Delta_{1:N})$$

Spearman rank correlation between signal strength and actual returns over a rolling lookback window (default 60 days). $\text{IC} > 0$ indicates the system's conviction directionally predicts returns.

### 8.3 Macro Risk Score

> Source: [`engines/macro_data.py` → `get_macro_regime_context()`](engines/macro_data.py)

Composite risk score from four macro indicators:

$$R_{\text{macro}} = \frac{R_{\text{rate}} + R_{\text{fx}} + R_{\text{inflation}} + R_{\text{growth}}}{4}$$

where each component $R_i \in [0, 1]$ is a normalized risk measure:
- $R_{\text{rate}}$: CBE interest rate vs thresholds (>18% → HIGH)
- $R_{\text{fx}}$: USD/EGP depreciation stress
- $R_{\text{inflation}}$: CPI YoY vs thresholds (>20% → HIGH)
- $R_{\text{growth}}$: GDP growth momentum (inverted: low growth → high risk)

**Macro-Adjusted Simulation** (`SimulationConfig`):

$$\mu^{\text{adj}} = \mu \times (1 - R_{\text{macro}} \times 0.3)$$

$$\sigma^{\text{adj}} = \sigma \times (1 + 0.15 \times \mathbf{1}[R_{\text{rate}} = \text{HIGH}])$$

---

## 9. Circuit Breaker

> Source: [`engines/circuit_breaker.py`](engines/circuit_breaker.py)

If portfolio maximum drawdown breaches the target threshold, the circuit breaker reduces equity exposure and raises cash:

**Excess Drawdown Ratio**

$$\epsilon = \frac{|\text{drawdown}| - \text{target\_drawdown}}{\text{target\_drawdown}}$$

**Additional Cash Raise**

$$\Delta\text{cash} = \min(15\%, \; 10\% + \epsilon \times 5\%)$$

**Re-scaling of Invested Positions**

$$f_{\text{new}} = 1 - \min(\text{max\_cash\_pct},\; \text{cash} + \Delta\text{cash})$$

$$\text{alloc}_i^{\text{new}} = \text{alloc}_i^{\text{old}} \times \frac{f_{\text{new}}}{1 - \text{cash}^{\text{old}}}$$

Positions are scaled proportionally so their relative weights remain unchanged but total invested exposure shrinks. The breaker fires if $|\text{drawdown}| > \text{target\_drawdown\_pct}$ and is logged with `circuit_breaker_triggered = True`.

---

## 14. Tier 2 Cost Gate (Horizon-scaled)

**Source:** `run_agents.py` `_compute_atr_pct` + Tier 2 gate (lines ≈ 1254–1278)

The cost gate rejects any UP/DOWN signal whose expected 5-day move cannot clear round-trip transaction cost plus a minimum net-profit margin.

**1-day ATR% (current bar):**

$$\text{ATR}_{1d}(\%) = \frac{\text{ATR}_{14}}{\text{close}} \times 100$$

**Horizon-adjusted expected move (5-day hold):**

$$E[\text{move}_{5d}](\%) = \text{ATR}_{1d}(\%) \times \sqrt{5} \approx \text{ATR}_{1d}(\%) \times 2.236$$

**Gate condition:**

$$\text{signal} \to \text{HOLD} \quad \text{if} \quad E[\text{move}_{5d}] < (c_{\text{round\_trip}} + m_{\text{min\_net}})$$

Where (EGX):
- $c_{\text{round\_trip}} = 0.5\%$ (spread + impact estimate)
- $m_{\text{min\_net}} = 1.0\%$ (minimum net profit over horizon)
- Threshold $= 1.5\%$

For Tadawul (KSA): $c_{\text{round\_trip}} = 0.4\%$, $m_{\text{min\_net}} = 1.0\%$, threshold $= 1.4\%$.

---

## 15. KPI Sample-Reliability Flag

**Source:** `web-ui/routes/track-record.js` `kpiForWindow`

Each rolling KPI window (30d / 60d / 90d / 180d / 365d) is tagged with a reliability level based on the count of evaluated trades $N$:

$$\text{reliability} = \begin{cases}
\text{high}         & \text{if } N \geq 30 \\
\text{preliminary}  & \text{if } 10 \leq N < 30 \\
\text{insufficient} & \text{if } N < 10
\end{cases}$$

Ratio metrics (Sharpe, Sortino, max-drawdown, profit factor) are dominated by noise below $N \approx 30$. The flag drives an amber/red "preliminary" badge on the track-record UI so investors interpret post-gate metrics correctly.

---

## 16. Market-Adjusted Data Age

**Source:** `web-ui/server.js` `marketAdjustedAgeHours`

For sources that only refresh on trading days (prices, predictions, consensus, sentiment, fx_rates), the `/api/intelligence/quality` endpoint reports a market-adjusted age instead of calendar age:

$$\text{age}_{\text{adj}} = \text{age}_{\text{cal}} - \sum_{d \in \text{weekend}} h_d$$

Where weekend for EGX/Tadawul = {Friday (UTC dow 5), Saturday (UTC dow 6)}. This prevents Thursday post-market data from triggering a false "stale" warning on Fri/Sat/Sun-morning.

---

*Last updated: April 2026 — reflects production codebase at HEAD.*
