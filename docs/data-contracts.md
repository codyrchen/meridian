# Data Contracts

Naming follows the implemented schema (`migrations/versions/`,
`packages/pipelines/src/meridian_pipelines/tables.py`); corrections and
conventions are recorded in `docs/decision-log.md`.

## Canonical entities

Implemented:
- `asset`: chain-aware token identity.
- `unlock_event`: canonical release event, stored as SCD2 versions.
- `unlock_event_source`: event-version ↔ source-artifact links with role and
  claim.
- `vesting_series`: stable identity for schedules whose tranches repeat.
- `supply_observation`: point-in-time supply per asset/date with method.
- `market_bar_daily`: point-in-time daily close/volume/market-cap observations.
- `source_artifact`: immutable raw payload or document metadata.

Deferred: `protocol`, `liquidity_snapshot`, `lineage_edge` (lineage carried by
FKs today), `research_run` (per-run `run_manifest.json` for now),
`model_version`.

## source_artifact

Required: `id`, `source_name`, `retrieved_at`, `knowledge_timestamp`,
`checksum_sha256`, `license_class`, `object_uri`, `metadata`.
Optional: `source_uri`. `UNIQUE (source_name, checksum_sha256)`; re-archiving
an identical payload dedupes; archives are never overwritten.

Storage default: raw bytes live in the gitignored content-addressed store
(`data/raw/<source_name>/<sha256>.raw`) referenced by `file://` URIs. Curation
files commit metadata, checksum, retrieval time, and a short excerpt/locator.
Full snapshots are committed under `data/curated/sources/` only when the
license explicitly permits redistribution.

## asset

Required: `id`, `symbol`, `name`, `valid_from`. Optional: `chain_id`,
`contract_address`, `decimals`, `coingecko_id`, `valid_to`.
`UNIQUE (chain_id, contract_address, valid_from)`.

## unlock_event (versioned)

Every row is one *version* of a logical event:

- `event_version_id` — primary key, unique per version.
- `logical_event_id` — stable across revisions; deterministic
  uuid5(asset, scheduled_at, allocation_bucket). Amount is excluded so a
  corrected amount keeps the same logical identity.
- `supersedes_version_id` — nullable self-FK chaining corrections.
- `valid_from` / `valid_to` / `knowledge_timestamp` — SCD2. Closing the old
  version's `valid_to` at supersede time is the single permitted UPDATE.
- One current version (`valid_to IS NULL`) per logical event, enforced by a
  partial unique index. Seeding conflicts against this index (idempotent
  no-op); revisions go through the explicit supersede operation, which also
  carries source links onto the new version.

Fields per version — required: `asset_id`, `scheduled_at` (UTC),
`event_kind` (`scheduled | observed_transfer | observed_exchange_deposit` —
scheduled unlocks are never merged with observed on-chain flows),
`release_type` (`cliff | linear | emission | milestone | governance |
unknown`), `allocation_bucket` (`team | investor | foundation | community |
ecosystem | treasury | airdrop | rewards | unknown`), `amount_tokens`
(NUMERIC(50,18), CHECK > 0), `amount_provenance` (`reported | derived`; a
derived amount requires a recorded `derivation`), `source_confidence`
(`verified_primary | verified_secondary | unverified`).

Optional (null rather than imputed): `transferable_at`, `bucket_composition`
(JSONB list of constituents for unsplit combined tranches; aggregator-sourced
splits live here, never in `allocation_bucket`), `derivation`,
`percent_current_circulating` (only when primary-reported point-in-time),
`percent_total_supply` (derived with recorded formula), `vesting_series_id`,
`tranche_number` (1-based), `ambiguity_flags`.

Enum vocabularies are enforced with CHECK constraints.

## unlock_event_source

PK `(event_version_id, source_artifact_id, source_role, claim_type)`.
`source_role ∈ primary | secondary_cross_check | onchain_verification`;
`claim_type ∈ schedule | amount | allocation | composition | supply | other`;
`excerpt` holds the supporting excerpt or locator. One event version links to
many artifacts; a multi-source curation record is never reduced to a single
artifact FK. Every current version must have at least one `primary` link
(curation-validity check, exercised by the report pipeline).

## vesting_series

`id` (deterministic uuid5(asset, series_slug)), `asset_id`, `series_slug`,
`name`, `cadence` (`cliff | monthly | quarterly | continuous | irregular |
unknown`), `tranche_count`, `first_tranche_at`, `last_tranche_at`, `notes`.
`UNIQUE (asset_id, series_slug)`. Tranches of one schedule share the series
id so analysis can treat repeated tranches as non-independent.

## supply_observation

PK `(asset_id, ts, source_artifact_id, method)`.
`method ∈ reported | implied_market_cap`; at least one of
`circulating_supply` / `total_supply` (CHECK), both positive when present;
`knowledge_timestamp` required. Research reads the latest observation at day
−1 preferring `reported`; estimates are stamped with their method and never
written back onto the canonical event.

## market_bar_daily

Unchanged from Epic 0: PK `(asset_id, ts, source_artifact_id)`; UTC calendar
`ts`; `close` required (CHECK > 0), OHLC nullable (CoinGecko supplies daily
price points); `quote_currency` required; append-only corrections; readers
take the latest `knowledge_timestamp` per `(asset_id, ts)`.

## Point-in-time rule

A prediction for timestamp T may only use records whose
`knowledge_timestamp <= T`. For events this is implemented by
`event_versions_as_of`: the latest version per logical event known at T.
Backfills must not retroactively leak corrected schedules into historical
predictions.

## Validation layers

1. **Curation validity** (is the event canonical?): template-v2 schema and
   taxonomy, archive checksums, derivation presence for derived amounts,
   primary-source backing for schedule and amount claims, duplicate detection
   among current versions, primary source links present.
   Entry points: `validate-curation` CLI (per file, no DB) and the
   `dq_checks` curation-layer functions.
2. **Research readiness** (may the event enter event-study output?): market
   and benchmark coverage over the full window, supply coverage, no missing
   days. An event with missing prices remains canonical but is blocked from
   research output and reported as such. No interpolation or imputation,
   ever.
