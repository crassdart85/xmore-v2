# Xmore Project - 5 Key Improvement Recommendations

## 1. Move Hardcoded Secrets to Environment Variables

**Problem:** API keys and email credentials are hardcoded directly in `config.py` (lines 35, 70-72) and committed to the repository. The NEWS_API_KEY, SMTP email, and email password are all exposed in plaintext. The n8n automation script also contains a hardcoded email address.

**Recommendation:**
- Create a `.env` file (already in `.gitignore`) and load secrets using `python-dotenv` or `os.getenv()`.
- Replace all hardcoded credentials in `config.py` with environment variable lookups.
- Rotate all currently exposed keys immediately since they exist in git history.
- Example: `NEWS_API_KEY = os.getenv('NEWS_API_KEY', '')` instead of the raw string.

**Impact:** Prevents credential leakage and is a prerequisite for any public or shared deployment.

---

## 2. Fix SQL Injection Vulnerability in MLAgent

**Problem:** In `agents/agent_ml.py` (line 47), a raw f-string is used to build a SQL query:
```python
news_df = pd.read_sql(f"SELECT date, sentiment_score FROM news WHERE symbol='{symbol}'", conn)
```
This is vulnerable to SQL injection if the `symbol` value is ever derived from user input or corrupted data.

**Recommendation:**
- Use parameterized queries instead:
  ```python
  news_df = pd.read_sql("SELECT date, sentiment_score FROM news WHERE symbol=?", conn, params=(symbol,))
  ```
- Audit all other database queries across the codebase for the same pattern.

**Impact:** Eliminates a common security vulnerability (OWASP Top 10) and follows secure coding best practices.

---

## 3. Improve Data Accumulation Strategy for Model Training

**Problem:** The model requires 50+ data points per stock to begin training (`train_model.py` line 31), but `collect_data.py` only fetches 5 days at a time and `quick_backfill.py` only provides ~60 days. After indicator calculations and the 7-day forward shift consume rows, there is often not enough data left to train. This means the ML model never actually trains, and all predictions default to "HOLD".

**Recommendation:**
- Increase the backfill script to fetch at least 6-12 months of historical data (yfinance supports `period="1y"` or `period="2y"`).
- Make `run_pipeline.py` check whether a trained model exists before calling `train_model.py`, and only retrain weekly or when sufficient new data has accumulated.
- Add a data sufficiency check at the start of the pipeline that warns clearly if training is impossible.
- Consider reducing the minimum data threshold or using models that work well with smaller datasets (e.g., gradient boosting with fewer features).

**Impact:** The ML model will actually train and produce meaningful UP/DOWN predictions instead of always falling back to HOLD.

---

## 4. Add Authentication and Rate Limiting to the Web Dashboard

**Problem:** The Express.js dashboard (`web-ui/server.js`) has no authentication or rate limiting. Anyone who can reach port 3000 on the network can access all predictions, stock prices, performance data, and system statistics. The API endpoints are also unprotected.

**Recommendation:**
- Add basic authentication middleware (e.g., `express-basic-auth` or session-based login) to protect the dashboard.
- Implement rate limiting on API endpoints using `express-rate-limit` to prevent abuse.
- Add a `/api/health` endpoint separate from `/api/stats` for the n8n health check, so monitoring doesn't require access to sensitive data.
- For production deployment (Vercel config already exists), add proper authentication via JWT or OAuth.

**Impact:** Protects sensitive financial predictions and system internals from unauthorized access.

---

## 5. Implement Retry Logic and Structured Logging Across the Pipeline

**Problem:** While `config.py` defines `MAX_RETRIES = 3` and `RETRY_DELAY_SECONDS = 5`, these values are never used. Each script makes a single attempt at API calls (yfinance, NewsAPI, FinBERT), and any transient failure (network timeout, API rate limit, temporary outage) causes a full step failure. Logging is inconsistent -- some scripts use `print()`, others use the `logging` module, and the n8n automation has its own error handling layer on top.

**Recommendation:**
- Implement a shared retry decorator or utility function that uses the existing `MAX_RETRIES` and `RETRY_DELAY_SECONDS` config values, with exponential backoff.
- Standardize all output to use Python's `logging` module instead of `print()`, with a consistent format that includes timestamps and log levels.
- Write logs to the configured `LOG_FILE` path (`logs/trading_system.log`) so the n8n automation and dashboard can reference them.
- Add a `--verbose` flag to scripts for debug-level output during development.

**Impact:** Makes the pipeline resilient to transient failures (which are common with financial APIs) and provides a single, consistent log trail for debugging issues.
