# Workplan: Epic 1 — Verified Historical Unlock Dataset

Status: approved with revisions 2026-08-04. Goal: 30–50 manually verified
historical unlock events across ~3–5 tokens, with lineage, point-in-time
correctness, and per-event plus pooled *descriptive* outputs.

Non-goals: frontend, ML, AI research assistant, trading execution, automated
document parsing, pooled statistical inference, aggregator-sourced facts.

## Approved decisions (2026-08-04)

1. **Price history**: free CoinGecko path. Provider history availability is a
   runtime research-coverage constraint, never a dataset definition. The
   connector stays provider-independent enough that a licensed source can be
   added later (payload fetching is already injected via `PayloadFetcher`;
   the parser is CoinGecko-specific and stays in `meridian_connectors`).
   No paid key for Epic 1.
2. **Initial tokens**: ARB, APT, SUI enter eligibility and curation first.
   OP, STRK, and other candidates require a primary-source eligibility audit
   before admission. No token is admitted merely to reach a count target.
3. **Clean window**: ±7 calendar days is the default clean-window
   *annotation*. It never removes events from the canonical dataset.

## Required design changes (incorporated)

### A. Multi-source lineage
`unlock_event_source` association table: one event version links to many
artifacts. Columns: `event_version_id`, `source_artifact_id`, `source_role`
(`primary | secondary_cross_check | onchain_verification`), `claim_type`
(`schedule | amount | allocation | composition | supply | other`), `excerpt`
(supporting excerpt or locator). A multi-source curation record is never
reduced to a single `source_artifact_id`; that column is dropped from
`unlock_event` (existing links migrate into the association table as
`primary`/`other`).

### B. Vesting-series identity
`vesting_series` table: `id` (deterministic from asset + series slug),
`asset_id`, `series_slug`, `name`, `cadence`
(`cliff | monthly | quarterly | continuous | irregular | unknown`),
`tranche_count`, `first_tranche_at`, `last_tranche_at`, `notes`.
`unlock_event` gains `vesting_series_id` and `tranche_number` so tranches of
one schedule share a stable series identifier and later analysis can model
repeated tranches as non-independent.

### C. Revision identity
`unlock_event` becomes explicitly versioned:
- `logical_event_id` — stable across revisions; deterministic
  uuid5(asset, scheduled_at, allocation_bucket). Amount is excluded so a
  corrected amount stays the same logical event.
- `event_version_id` — PK, unique per version; deterministic
  uuid5(logical_event_id, knowledge_timestamp, amount).
- `supersedes_version_id` — nullable self-FK.
- `valid_from`, `valid_to`, `knowledge_timestamp` — SCD2. Closing the old
  version's `valid_to` at supersede time is the single permitted UPDATE;
  no row is ever deleted or rewritten.
- Partial unique index: one current version (`valid_to IS NULL`) per
  `logical_event_id`. Seeding is idempotent against this index; revisions
  happen only through the explicit supersede operation.
- Query helpers: `current_event_versions` (valid_to IS NULL) and
  `event_versions_as_of(knowledge_ts)` (latest version whose
  knowledge_timestamp <= ts, per logical event). Both are integration-tested.

### D. Two validation layers
1. **Curation validity** — provenance, checksum integrity, derivation
   presence, taxonomy, schedule sanity, duplicates. An event failing these is
   not canonical.
2. **Research readiness** — market-data coverage, benchmark coverage, supply
   coverage, complete windows. An event with missing prices remains a valid
   canonical event but is blocked from event-study output and listed in the
   coverage report.

### E. Source storage and licensing
Public accessibility does not authorize redistribution. Default: raw archived
bytes live in the gitignored content-addressed store (`data/raw/`), while the
curation file commits metadata, checksum, retrieval time, and a short
excerpt/locator. Full snapshots are committed (`data/curated/sources/`) only
when the license explicitly permits (`redistributable: true` in the curation
file). The Epic 0 ARB snapshots remain committed under the previously logged
exception.

## Plan sections (revised summary)

1. **Token selection**: primary documentation exists; discrete events; price
   coverage across all windows; ≥5 verifiable events; diversity. Free-tier
   history (~365 days) is recorded per-token as a coverage constraint at
   ingest time, not baked into the dataset definition.
2. **Inclusion/exclusion**: discrete scheduled unlocks in; continuous
   emission, unverifiable schedules, TGE day, uncovered windows out. Every
   exclusion recorded in `data/curated/exclusions.yaml` with a reason.
3. **Verification**: date and cadence from primary sources; amount reported
   or derived from primary-verified quantities with recorded formula;
   archived checksummed sources; secondary cross-check recorded with an
   agree/disagree verdict; disagreement blocks ingestion.
4. **Archiving workflow**: manual fetch; bytes stored content-addressed by
   sha256; curation file records URL, retrieval time, checksum, license,
   excerpt; loader re-hashes before any DB write.
5. **Reported vs derived**: `amount_provenance` + `derivation` columns;
   curation file mirrors with verified_facts / derived_values; derived
   without derivation is rejected at the domain and curation layers.
6. **Bucket taxonomy**: existing 9-value enum with binding mapping rules in
   the curation guide; unsplit combined tranches use `unknown` +
   `bucket_composition` (aggregator splits never enter `allocation_bucket`).
7. **Point-in-time supply**: `supply_observation` table
   (`reported | implied_market_cap`); research reads latest observation at
   day −1 preferring `reported`; canonical `percent_current_circulating`
   stays null unless primary-reported.
8. **Percent calcs**: `percent_total_supply` derived at curation with
   recorded formula; percent-of-float computed at research time from
   `supply_observation`, stamped with method, never written to the event.
9. **Overlaps**: overlap metadata per event (count/offsets/sizes in window,
   nearest-event distance); ±7d clean-window boolean annotation; cross-token
   same-day clustering reported; nothing dropped.
10. **Missing data**: missing prices ⇒ research-blocked, canonically valid;
    missing supply ⇒ null percent + flag; coverage report is a first-class
    output; no interpolation.
11. **Confidence & revisions**: vocabulary unchanged; `verified_secondary`
    only for composition-level detail; revisions per (C).
12. **Batch config**: `config/dataset.yaml` + one curation file per event
    under `data/curated/unlock_events/<token>/`; Epic 0 `slice.yaml` intact.
13. **Schema**: migration 0002 (this stage; see A–C, supply_observation).
14. **Batch ingestion**: span-union fetch planning, 92-day daily-granularity
    floor, idempotent seeding/ingestion, per-token loud failures (later
    stage).
15. **Dataset validation**: `validate-dataset` implementing layers (D)
    (later stage).
16. **Outputs**: per-event artifact triple + `events_master.csv`,
    `panel_long.csv`, `pooled_summary.csv`, pooled CAR chart, dataset
    manifest; deterministic ordering; offline fixture mode (later stage).
17. **Tests**: see stage plans; Epic 0 suite preserved throughout.
18. **Acceptance criteria** (dataset-complete): every event links to ≥1
    archived primary artifact re-hashing to its recorded checksum; all
    exclusions recorded; validate-dataset green; provenance populated;
    idempotent re-runs insert zero rows; pooled artifacts reproducible;
    migrations roundtrip; Epic 0 commands and tests intact; gate green.
19. **Files**: see stage plans.
20. **Sequence**: foundation stage (below) → curation tooling/batch seed →
    batch ingestion + supply → overlap + validation → pooled outputs →
    token-by-token curated ingestion → full dataset run + docs.

## Foundation stage (this implementation)

Scope:
1. This workplan + decision-log entries.
2. Migration 0002: provenance fields, logical/versioned identity,
   vesting-series representation, `unlock_event_source`,
   `supply_observation`; deterministic backfill; full downgrade.
3. Curation schema (template v2 validator), event template, exclusions
   template, curation guide, `validate-curation` CLI.
4. Migration and curation-validation tests; revision-flow tests
   (current-state and as-of queries).
5. Epic 0 commands and tests preserved (mechanical updates only where the
   approved rename requires it); `arb.yaml` re-expressed in template v2 with
   identical facts.

Explicitly deferred: curating 30–50 events, batch market ingestion, pooled
reports, frontend, ML, automated source parsing.
