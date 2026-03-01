# News RAG Integration Layer (Mar 1, 2026)

## Architecture
- **Use Case 1**: Contextual Q&A — recency-weighted semantic retrieval + Gemini synthesis
- **Use Case 2**: Simulation drift adjustment — news triggers μ recalibration in Monte Carlo engine
- **Embedding model**: Gemini `text-embedding-004` (768-dim) — same as existing RAG system
- **Vector store**: New `news_rag_chunks` table in main DB (not chromadb/faiss)
- **Drift audit**: `drift_adjustment_log` table with SHA-256 audit hashes

## Module Structure (Python — `news/` package at project root)
```
news/
├── models.py              — Pydantic models: RawArticle, ProcessedChunk, DriftAdjustmentRecord
├── sources/
│   ├── base.py            — Abstract BaseNewsSource
│   ├── rss_source.py      — RSS/Atom connector (feedparser + trafilatura body extraction)
│   └── registry.py        — ALL_SOURCES list (EGX_SOURCES + MACRO_SOURCES)
├── pipeline/
│   ├── deduplicator.py    — 2-stage: SHA-256 hash + Jaccard title similarity (no sentence-transformers)
│   ├── chunker.py         — Word-level chunking (300 words, 60 overlap), title prepended
│   ├── embedder.py        — Gemini text-embedding-004 wrapper (0.12s rate limit)
│   ├── storage.py         — upsert_chunks() to news_rag_chunks table
│   └── ingestion.py       — NewsIngestionPipeline.run_cycle() orchestrator
├── classifier/
│   ├── event_classifier.py — Keyword rules (bilingual EN+AR) + Gemini LLM fallback
│   └── asset_mapper.py    — Company name → EGX ticker + sector keyword mapping
├── retrieval/
│   ├── retriever.py       — retrieve_news_chunks() + retrieve_combined(); score = sim*recency*source_weight
│   └── synthesizer.py     — Gemini 2.0 Flash synthesis with institutional-grade prompt
├── drift/
│   ├── decay_model.py     — ExponentialDecayModel: eff_adj = adj_bps * exp(-t*ln2/halflife)
│   ├── audit_log.py       — AuditLog: log()/get_active_adjustments()/verify_integrity()
│   └── adjustment_engine.py — DriftAdjustmentEngine + get_net_drift_adjustment(ticker) singleton
├── scheduler.py           — APScheduler (15-min cycle + 21:00 UTC catch-up)
├── ask_cli.py             — CLI for Node.js Q&A subprocess (JSON stdout)
├── ingest_cli.py          — CLI for manual/CI ingestion
└── drift_cli.py           — CLI for drift query (ticker/recent/verify)
```

## DB Tables (new)
- **`news_rag_chunks`**: id (UUID), article_url, source_name, title, content, chunk_index, published_at, ingested_at, language, market_tag, event_type, affected_assets (JSON), affected_sectors (JSON), drift_direction, drift_magnitude_estimate, embedding (JSON)
- **`drift_adjustment_log`**: adjustment_id, chunk_id, asset_ticker, original_drift, adjustment_bps, adjusted_drift, decay_halflife_days, applied_at, expires_at, event_type, source_headline, confidence, applied_by, audit_hash

## Node.js API Endpoints (added to `web-ui/routes/rag.js`)
- `POST /api/rag/news/ask` — Q&A: `{question, market?, portfolio?, language?, source_mode?}` → spawns ask_cli.py
- `GET  /api/rag/news/chunks` — Browse ingested chunks (query params: market, event_type, limit)
- `POST /api/rag/news/ingest` — Trigger manual ingestion cycle (background)
- `GET  /api/rag/drift/:ticker` — Current decayed drift adjustments for a ticker
- `GET  /api/rag/drift` — Recent drift adjustments (all tickers, ?limit=50)
- `GET  /api/rag/drift/verify/:id` — Audit hash integrity check

## SimulationEngine Integration
- `engines/simulation_core.py`: `_apply_news_drift_adjustments()` called at end of `fit()`
- Queries `get_net_drift_adjustment(symbol)` per asset; adds `adj_bps/10000/252` to `_static_mu[i]`
- Graceful degradation: silently skips if `news` module not importable

## Drift Impact Table (calibration starting points)
- RATE_DECISION: 150bps, 10d halflife, sector scope
- FX_MOVE: 200bps, 7d halflife, market scope
- EARNINGS_RELEASE: 250bps, 5d halflife, asset scope
- IMF_WORLD_BANK: 180bps, 14d halflife, market scope
- MACRO_DATA: 100bps, 7d halflife, market scope

## Event Types
RATE_DECISION | FX_MOVE | EARNINGS_RELEASE | REGULATORY_CHANGE | MACRO_DATA | IMF_WORLD_BANK | GEOPOLITICAL | CORPORATE_ACTION | IPO | GENERAL | IRRELEVANT

## CI/CD
- `news/ingest_cli.py` added as step in `intraday-news-update` job (continue-on-error: true)
- Requires `GOOGLE_API_KEY` secret (same as existing Gemini integration)

## New Dependencies
- `trafilatura>=1.8.0` — full article body extraction (added to both requirements.txt and requirements-web.txt)
- `feedparser`, `APScheduler`, `pydantic`, `beautifulsoup4`, `google-genai` already present

## Key Design Decisions
- Use Gemini text-embedding-004 (NOT sentence-transformers) — consistent with existing RAG
- Use existing SQLite/PG DB (NOT chromadb/faiss) — single system of record
- Use existing get_connection() abstraction — no SQLAlchemy added
- Jaccard shingle similarity for semantic dedup (NOT local embedding model)
- Conservative drift trigger: first chunk only, direction != UNCERTAIN, assets resolved
- Max drift cap: ±500 bps annualized (prevents runaway parameter drift)
