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

## Epic 1 decisions (2026-08-04)

### Free CoinGecko path; provider-independent coverage
- Date: 2026-08-04
- Decision: Epic 1 uses the free CoinGecko path. Provider history availability (~365 days of daily data) is treated as a runtime research-coverage constraint reported per event, never as a permanent dataset definition. The connector remains provider-independent (injected payload fetcher; provider-specific parsing isolated in meridian_connectors) so a licensed source can be added later. No paid key is purchased or required.
- Context: free-tier history limits which historical events can be priced, but the canonical dataset must not inherit a vendor's window.
- Revisit trigger: licensing a longer-history market-data source.

### Initial tokens ARB, APT, SUI; eligibility audit for all others
- Date: 2026-08-04
- Decision: eligibility and curation begin with ARB, APT, SUI. OP, STRK, and further candidates must pass a primary-source eligibility audit first. A token is never admitted merely to meet a token-count target.
- Context: dataset trustworthiness outranks dataset size (see "Curated dataset before automated extraction").

### Clean-window annotation, ±7 calendar days
- Date: 2026-08-04
- Decision: events with another same-asset event within ±7 calendar days of day 0 are annotated as not clean-window. The flag is descriptive metadata for downstream filtering and must never remove events from the canonical dataset.
- Context: monthly cadences make ±30-day windows overlap by construction; dropping overlapped events would bias toward cliff-only tokens.

### Multi-source event lineage (unlock_event_source)
- Date: 2026-08-04
- Decision: one event version links to many source artifacts through unlock_event_source (event_version_id, source_artifact_id, source_role primary|secondary_cross_check|onchain_verification, claim_type schedule|amount|allocation|composition|supply|other, excerpt/locator). unlock_event.source_artifact_id is dropped; existing links migrate as role=primary. A multi-source curation record is never reduced to one artifact FK.
- Context: real events rest on several documents plus optional on-chain verification; a single FK forced information loss.
- Consequences: "every event links to >=1 archived primary source" is enforced by the curation-validity layer, not a NOT NULL column.

### Versioned event identity (logical_event_id / event_version_id)
- Date: 2026-08-04
- Decision: unlock_event rows are versions. logical_event_id = uuid5(asset, scheduled_at, allocation_bucket) is stable across revisions (amount excluded so corrections keep identity). event_version_id (PK) = uuid5(logical_event_id, knowledge_timestamp, amount). supersedes_version_id chains versions. SCD2 valid_from/valid_to with a partial unique index enforcing one current version per logical event. Closing valid_to at supersede time is the single permitted UPDATE. Current-state and as-of query helpers are provided and integration-tested.
- Context: modeling revisions as unrelated deterministic rows made correction history unqueryable and risked duplicate current rows.

### Vesting-series identity
- Date: 2026-08-04
- Decision: vesting_series table (deterministic id from asset + series slug; cadence, tranche_count, first/last tranche timestamps) with unlock_event.vesting_series_id and tranche_number. Tranches of one schedule share a stable series id.
- Context: monthly tranches are not independent observations; later analysis needs the grouping to model repeated events honestly.

### Two validation layers: curation validity vs research readiness
- Date: 2026-08-04
- Decision: curation validity (provenance, checksums, derivation, taxonomy, schedule, duplicates) decides whether an event is canonical. Research readiness (market/benchmark/supply coverage, complete windows) decides whether it enters event-study output. An event with missing prices stays canonical but is research-blocked and reported as such.
- Context: conflating the layers either fabricated coverage or ejected verified facts from the dataset.

### Source storage defaults to gitignored; metadata-only commits
- Date: 2026-08-04
- Decision: archived source bytes default to the gitignored content-addressed store (data/raw/). Curation files commit metadata, checksum, retrieval time, and a short excerpt/locator. Full snapshots are committed under data/curated/sources/ only when the license explicitly permits redistribution (redistributable: true). Existing Epic 0 ARB snapshots stay committed under the previously logged exception.
- Context: public accessibility does not authorize redistribution.
