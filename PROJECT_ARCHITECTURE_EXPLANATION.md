# Xmore Technical Whitepaper

## Executive Summary

Xmore is an intelligence platform for equity decision support, centered on the Saudi Exchange (Tadawul) and extended to selected global and ETF workflows. The platform combines a scheduled Python intelligence engine with a Node.js application layer, backed by a shared relational data model.

In production, Xmore is designed to:

- Continuously ingest market and news signals.
- Generate multi-agent directional intelligence.
- Apply risk and execution realism before surfacing actionable ideas.
- Measure realized outcomes against benchmarks and costs.
- Provide research and explainability through retrieval-augmented interfaces.

This document describes the operating architecture as implemented today.

## 1) System Purpose and Product Model

Xmore is built for decision support rather than direct trade routing. It helps investment teams and market participants move from raw market data to risk-aware, explainable signal intelligence.

The current system serves four product goals:

1. Timely market state visibility (prices, sentiment, macro context, ETF state).
2. Structured signal generation using independent agent families.
3. Risk-aware signal filtering and execution feasibility checks.
4. Transparent performance tracking and research-grade explanation.

The platform is therefore best described as an intelligence and analytics stack with simulated execution controls, not a broker-connected execution engine.

## 2) Architecture Overview

Xmore follows a split-plane architecture:

- Intelligence plane (Python): data ingestion, signal generation, screening, simulation, and evaluation.
- Application plane (Node.js/Express): API delivery, authentication/session handling, static frontend hosting, admin workflows, and orchestration endpoints.
- Data plane (PostgreSQL in deployed environments, SQLite fallback locally): shared state for both planes.

High-level flow:

```text
External data and model providers
      ->
Scheduled intelligence jobs (Python)
      ->
Shared relational store
      ->
Application API and web surfaces (Node.js)
      ->
End users, admins, and downstream consumers
```

A key implementation characteristic is runtime separation: compute-heavy intelligence jobs run on scheduled automation, while the web tier focuses on serving and interaction.

## 3) Data and Intelligence Pipeline

## 3.1 Market and news ingestion

The ingestion layer collects:

- Tadawul market prices through a primary live-feed path with fallback providers.
- Global and macro reference series used for context and filtering.
- News from API, RSS, and curated source pipelines.

Ingestion writes normalized records to the core store and logs data quality signals (such as missing continuity or unusual jumps), enabling operational diagnostics and downstream trust controls.

## 3.2 Signal generation pipeline

Xmore uses a multi-agent signal stack that combines different signal philosophies:

- momentum and oscillator style agents,
- trend and moving-average agents,
- volume behavior agents,
- machine-learning classifiers,
- optional model-driven enrichment components when enabled.

The pipeline computes per-symbol agent outputs, then aggregates them through a consensus stage that produces a unified signal object with confidence and reasoning metadata.

## 3.3 Consensus, risk gate, and regime gate

Consensus is layered, not a simple vote. In implementation, the architecture combines:

- weighted directional aggregation,
- bull/bear case construction,
- explicit risk gate actions (pass, flag, downgrade, block),
- market regime checks that can suppress or downgrade long bias in unfavorable states.

This layered approach is central to Xmore's quality model: every surfaced signal has already passed through multiple guardrails.

## 3.4 Execution realism

Before recommendations are surfaced as tradable ideas, Xmore applies execution realism controls that account for market frictions and practical feasibility. Controls include:

- liquidity-aware sizing,
- slippage and partial-fill assumptions,
- round-trip cost and edge-vs-cost checks,
- order splitting and stop-loss realism constraints.

The goal is to reduce model-to-market gap by filtering signals that are statistically attractive but operationally weak.

## 3.5 Evaluation and learning loops

Evaluation is continuous and multi-horizon:

- prediction outcomes are resolved once target windows pass,
- recommendation return fields are populated over short horizons,
- benchmark-relative fields (alpha and beat-rate) are updated,
- performance snapshots feed ranking and transparency surfaces.

This creates a closed loop from signal publication to realized measurement, enabling calibration and quality tracking over time.

## 3.6 Research and RAG layer

Xmore includes a research layer that unifies structured market state with document/news retrieval.

Current implementation supports:

- semantic retrieval over embedded reports and news chunks,
- vector search where available, with robust cosine fallback,
- explainability endpoints for "why this signal" style responses,
- recency-weighted news retrieval and event-aware synthesis,
- drift-adjustment hooks for simulation contexts, with auditable records.

This turns the platform from a pure signal feed into an explainable intelligence workspace.

## 4) Execution, Risk, and Performance Architecture

Xmore separates three concerns that are often mixed in single-stage systems:

- risk validity,
- execution feasibility,
- realized performance attribution.

### Risk architecture

Risk controls evaluate liquidity, volatility, drawdown behavior, signal-quality confidence, and concentration effects. Actions are explicit and stateful, allowing policy-level outcomes instead of hidden score adjustments.

### Execution architecture

Execution controls model practical friction and reject weak edge opportunities when expected return does not compensate for costs and fill constraints.

### Performance architecture

Performance metrics combine directional accuracy with market-relative and cost-aware analytics. The platform computes and exposes benchmark comparisons, alpha fields, drawdown-sensitive views, and risk-adjusted summaries.

From a due-diligence perspective, this separation improves traceability: users can inspect whether a weak result was due to prediction quality, risk suppression, or execution assumptions.

## 5) Platform Surfaces

Xmore exposes multiple product surfaces over the same core intelligence state.

## 5.1 API surface

The API layer includes domains for:

- market and signal state,
- trade recommendation and briefing flows,
- performance and track-record analytics,
- screening and ranked signals,
- portfolio forecast and simulation endpoints,
- RAG/research and ETF data domains,
- admin and operational endpoints.

The API architecture is modular within a single web service, which simplifies deployment while keeping domain boundaries clear.

## 5.2 Web experience

The web layer serves a multi-tab analytics experience with dedicated views for prediction flow, performance, track record, research, and operations.

It includes:

- language and localization support,
- authenticated user workflows,
- investor-facing transparency pages,
- admin-oriented management and ingestion controls.

## 5.3 Forecast and simulation experiences

Xmore includes both historical replay (time-machine style) and probabilistic forecast capabilities, giving users two complementary lenses:

- what historical signal behavior would have produced,
- what scenario-driven forward distributions imply.

## 6) Data Model and State Management

The data model is relational and domain-oriented. At a high level, it maintains:

- market and news facts,
- prediction and consensus state,
- recommendation and outcome state,
- user/auth/watchlist context,
- research embeddings and retrieval context,
- ETF and screening extensions,
- forecast and simulation result history.

Implementation supports both PostgreSQL and SQLite execution contexts with adapted SQL semantics and upsert behavior. This improves portability across local and hosted environments.

A practical consideration is dual schema bootstrap ownership across the Python and Node startup paths. This increases flexibility but requires disciplined schema governance to avoid drift.

## 7) Deployment and Operating Model

Xmore is operated as a split runtime:

- Web/API tier: hosted Node.js service with startup database bootstrap.
- Intelligence tier: scheduled Python jobs for intraday updates, post-market pipelines, nightly consolidation, evaluation catch-up, ETF workflows, and periodic backtests.
- Data tier: managed relational database with shared access by both runtimes.

Operationally, this architecture provides clear scaling boundaries:

- serving scale is managed independently from compute cadence,
- pipeline freshness depends on schedule health and external data/model availability,
- intelligence artifacts are persisted and then served on demand.

## 8) Security and Reliability Posture

Implemented controls include:

- HTTP hardening middleware,
- CORS policy handling,
- API rate limiting,
- JWT cookie-based authentication,
- password hashing and secure session handling.

Reliability patterns include:

- source failover in ingestion,
- idempotent upsert-oriented persistence,
- graceful degradation for optional capabilities,
- cached and asynchronous enrichment flows where appropriate.

This is a pragmatic production posture focused on continuity and controlled failure modes.

## 9) Technical Differentiation

Xmore differentiates through architecture, not only signal logic.

1. Split intelligence and application planes
   The platform keeps heavy analytics and user-serving concerns separate while sharing one canonical state model.

2. Multi-layer signal quality control
   Signals pass through consensus, risk gating, regime gating, and execution realism before publication.

3. Explainability integrated with live analytics
   Research endpoints combine retrieval context, market state, and signal-level reasoning rather than treating chat and analytics as separate products.

4. Market-aware performance transparency
   The platform tracks realized outcomes with benchmark-relative and cost-aware metrics, supporting institutional-style review.

5. Unified signal + simulation stack
   Historical replay, probabilistic forecasting, and live recommendation flows are connected through common data and risk abstractions.

## 10) Current Boundaries and Due-Diligence Notes

The current implementation has known boundaries that are important for buyers and partners:

- It is not a broker execution platform.
- External providers (market data, news, model APIs) are critical dependencies.
- Schema governance spans two runtime bootstraps and must be actively managed.
- Some frontend logic remains centralized, which can affect long-term maintainability.
- Optional fallback behavior improves uptime but can mask partial data degradation if not monitored.

These are common tradeoffs in fast-moving intelligence platforms and are visible in the current architecture.

## 11) Summary

Xmore is a production-oriented market intelligence platform with a clear architectural identity:

- scheduled Python intelligence generation,
- Node.js application delivery,
- shared relational state,
- layered controls for risk, execution realism, and performance accountability,
- integrated research and explainability capabilities.

For technical buyers and partners, the core value lies in how the platform connects ingestion, intelligence generation, risk-aware publication, and transparent evaluation into one coherent operating model.
