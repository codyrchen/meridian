# Data Contracts

Naming follows the implemented schema (`migrations/versions/0001_initial.py`,
`packages/pipelines/src/meridian_pipelines/tables.py`), which took
`sql/initial_schema.sql` as its baseline with corrections recorded in
`docs/decision-log.md`.

## Canonical entities

Implemented in Epic 0:
- `asset`: chain-aware token identity.
- `unlock_event`: canonical release event.
- `market_bar_daily`: point-in-time daily close/volume/market-cap observations.
- `source_artifact`: immutable source payload or document metadata.

Deferred (defined here, not yet implemented):
- `protocol`: project identity and category.
- `vesting_schedule`: source-specific schedule version.
- `liquidity_snapshot`: venue and depth metrics.
- `lineage_edge`: raw-to-normalized provenance beyond direct
  `source_artifact_id` foreign keys.
- `research_run`: replaced in Epic 0 by a per-run `run_manifest.json`
  artifact (code SHA, config hash, data snapshot, package versions).
- `model_version`: features, training window, metrics, calibration,
  artifact URI.

## source_artifact

Required: `id`, `source_name`, `retrieved_at`, `knowledge_timestamp`,
`checksum_sha256`, `license_class`, `object_uri`, `metadata`.
Optional: `source_uri`.

- `UNIQUE (source_name, checksum_sha256)`: re-archiving an identical payload
  dedupes; archives are never overwritten.
- `object_uri` uses `file://` paths locally (`data/raw/`, gitignored);
  curated primary-source snapshots for canonical events live under
  `data/curated/sources/` and are committed when `license_class` permits.

## asset

Required: `id`, `symbol`, `name`, `valid_from`.
Optional: `chain_id`, `contract_address`, `decimals`, `coingecko_id`,
`valid_to`. `UNIQUE (chain_id, contract_address, valid_from)`.

## unlock_event

Required:
- `id`
- `asset_id`
- `scheduled_at` (UTC)
- `release_type`: `cliff | linear | emission | milestone | governance | unknown`
- `allocation_bucket`: `team | investor | foundation | community | ecosystem |
  treasury | airdrop | rewards | unknown`
- `amount_tokens` (NUMERIC(50,18), CHECK > 0)
- `source_artifact_id`
- `source_confidence`: `verified_primary | verified_secondary | unverified`
- `knowledge_timestamp`
- `valid_from`

Optional (nullable by decision — record null rather than impute):
- `percent_current_circulating`
- `percent_total_supply`
- `transferable_at`
- `valid_to`
- `ambiguity_flags` (JSONB list; defaults to empty)

Deferred fields from the original contract: `observed_distribution_at`,
`exchange_deposit_at`, `schedule_version`, recipient labeling.

Enum vocabularies are enforced with CHECK constraints. Corrections are
append-only new rows (`valid_from`/`valid_to`), never destructive edits.

## market_bar_daily

Primary key `(asset_id, ts, source_artifact_id)`.

- `ts` is a UTC calendar date.
- `close` required (CHECK > 0); `open/high/low` nullable — the CoinGecko
  `market_chart/range` endpoint provides daily price points, not OHLC.
- `volume_usd`, `market_cap_usd` nullable, CHECK >= 0.
- `quote_currency` required (default `usd`) so every monetary value carries
  its currency.
- `source_artifact_id` and `knowledge_timestamp` required on every row.
- Corrections are append-only: a revised observation is a new row under a new
  source artifact. Readers select the row with the latest
  `knowledge_timestamp` per `(asset_id, ts)`.

## Point-in-time rule

A prediction for timestamp T may only use records whose
`knowledge_timestamp <= T`. Backfills must not retroactively leak corrected
schedules into historical predictions.

## Data-quality checks

Implemented in Epic 0 (`meridian_pipelines.dq_checks`):
- nonnegative prices and volumes (also enforced by CHECK constraints)
- duplicate unlock-event detection by asset/time/bucket/amount/source
- market coverage across the full event window (day -31 through +30),
  failing loudly on any missing day; no interpolation or imputation

Deferred: supply identities within tolerance, event amount vs remaining
allocation, token identity and contract-address consistency,
stale-source and revision alerts.
