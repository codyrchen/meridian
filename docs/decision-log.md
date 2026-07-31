# Decision Log

Use one entry per material decision.

## Template
- Date:
- Decision:
- Context:
- Alternatives considered:
- Why this choice:
- Consequences:
- Revisit trigger:

## Initial decisions
### Monorepo before microservices
Use a modular monolith with clear package boundaries. Revisit only after operational evidence shows independent scaling or ownership needs.

### Curated dataset before automated extraction
Build a small high-confidence dataset first. Automation without a gold set creates invisible errors.

### Daily data before intraday data
Daily observations are sufficient to test the core hypothesis and are easier to license, validate, and reproduce.

## Epic 0 decisions (2026-07-30)

### Vertical slice across roadmap phases
- Date: 2026-07-30
- Decision: Epic 0 cuts vertically across roadmap Phases 0-3 (scaffold, data model, one curated event, market data, event study) instead of completing phases horizontally.
- Context: CLAUDE.md and the implement-slice skill mandate the smallest end-to-end vertical slice; the roadmap describes horizontal layers.
- Alternatives considered: complete Phase 0 (scaffold only) first.
- Why this choice: an end-to-end slice validates every architectural boundary and the reproducibility story with one token before wider investment.
- Consequences: roadmap phases remain the layer map; delivery is sliced.
- Revisit trigger: none; the roadmap acceptance criteria still apply cumulatively.

### PostgreSQL 16 via Docker Compose, no TimescaleDB
- Date: 2026-07-30
- Decision: plain PostgreSQL 16 in Docker Compose for local development; TimescaleDB deferred.
- Context: README suggested "PostgreSQL + TimescaleDB initially"; architecture says "TimescaleDB or partitioned Postgres".
- Why this choice: daily bars for a handful of assets do not justify a time-series extension; NUMERIC precision requirements rule out SQLite.
- Revisit trigger: intraday data or >10k series.

### Event-time conventions and missing data
- Date: 2026-07-30
- Decision: daily UTC data; day 0 = the UTC calendar date of the unlock; event window [-30, +30]; a day -31 price is required so the day -30 return is computable; missing required observations fail loudly; no interpolation or silent imputation.
- Context: crypto trades continuously, so event days are calendar days, and no document previously fixed the convention.
- Revisit trigger: intraday event studies.

### Return methodology for Epic 0
- Date: 2026-07-30
- Decision: report raw cumulative ARB log return and BTC-adjusted CAR, where abnormal_return_t = ARB_log_return_t - BTC_log_return_t and CAR is the cumulative sum of abnormal returns. No beta-adjusted returns, factor models, hypothesis tests, or ML in Epic 0.
- Revisit trigger: Phase 3 event-study engine work (beta-adjusted benchmark required by MVP acceptance criteria).

### Raw artifact storage and git hygiene
- Date: 2026-07-30
- Decision: raw payloads archived immutably on the local filesystem under data/raw/ with file:// object URIs, checksums, and retrieval timestamps; only synthetic fixtures are committed; real API payloads and credentials stay out of git. Exception: manually curated primary-source snapshots for canonical unlock events (license_class public only, e.g. Arbitrum Foundation governance docs) are committed under data/curated/sources/ so the curated event's lineage survives a clean clone.
- Context: no object storage exists yet; CoinGecko terms restrict redistribution; CLAUDE.md forbids committing paid-source payloads. Public governance documentation carries no such restriction and every canonical event must link to a source artifact.
- Revisit trigger: introduction of object storage (schema unchanged; URIs swap).

### source_confidence vocabulary
- Date: 2026-07-30
- Decision: `verified_primary | verified_secondary | unverified`, enforced by a CHECK constraint.
- Context: the field was required by the data contracts but had no defined vocabulary.

### run_manifest.json instead of research_run table
- Date: 2026-07-30
- Decision: Epic 0 records reproducibility metadata (code SHA, config hash, data snapshot summary, package versions) in a run_manifest.json artifact per run; the research_run table is deferred to Phase 1.
- Revisit trigger: more than one research specification or consumer.

### Canonical naming and schema corrections
- Date: 2026-07-30
- Decision: sql/initial_schema.sql is the canonical naming baseline (id, scheduled_at, valid_from, market_bar_daily), corrected where CLAUDE.md requires: quote_currency added to market_bar_daily, CHECK constraints for release_type / allocation_bucket / source_confidence, supply-percentage fields nullable. docs/data-contracts.md is updated to match the implemented schema.
- Context: docs/data-contracts.md and the SQL draft disagreed on field names and nullability, and OHLC columns carried no currency designation.

### Frontend quality gates conditional on apps/web
- Date: 2026-07-30
- Decision: npm lint/typecheck/test gates run only when apps/web exists; the Makefile gate target skips them otherwise.
- Context: CLAUDE.md's gate assumed a web app that the roadmap defers to Phase 4.

### ARB event verification protocol
- Date: 2026-07-30
- Decision: the June 2026 monthly ARB investor/team unlock is the candidate event. Its timestamp, quantity, and allocation must be verified against an official Arbitrum source or the on-chain vesting contract before curation; the primary source is archived with retrieval timestamp and checksum; verified facts are distinguished from derived values; aggregators are secondary cross-checks only; if verification fails, stop and report.
- Context: aggregator-only sourcing creates invisible errors (see "Curated dataset before automated extraction").
