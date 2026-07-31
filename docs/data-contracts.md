# Data Contracts

## Canonical entities
- `asset`: chain-aware token identity.
- `protocol`: project identity and category.
- `vesting_schedule`: source-specific schedule version.
- `unlock_event`: canonical release event.
- `allocation_bucket`: team, investor, foundation, community, ecosystem, treasury, airdrop, rewards, unknown.
- `market_bar`: point-in-time OHLCV and market-cap observations.
- `liquidity_snapshot`: venue and depth metrics.
- `source_artifact`: immutable source payload or document metadata.
- `lineage_edge`: raw-to-normalized provenance.
- `research_run`: specification, code revision, data snapshot, outputs.
- `model_version`: features, training window, metrics, calibration, artifact URI.

## Unlock event fields
Required:
- event_id
- asset_id
- scheduled_at_utc
- release_type: cliff | linear | emission | milestone | governance | unknown
- allocation_bucket
- amount_tokens
- percent_current_circulating
- percent_total_supply
- source_artifact_id
- source_confidence
- knowledge_timestamp
- record_valid_from

Recommended:
- recipient_address or labeled entity when public and defensible
- transferable_at
- observed_distribution_at
- exchange_deposit_at
- schedule_version
- notes and ambiguity flags

## Point-in-time rule
A prediction for timestamp T may only use records whose `knowledge_timestamp <= T`. Backfills must not retroactively leak corrected schedules into historical predictions.

## Data-quality checks
- nonnegative amounts and prices
- supply identities within tolerance
- event amount does not exceed remaining allocation
- duplicate detection by asset/time/bucket/amount/source
- token identity and contract-address consistency
- market coverage around event window
- stale-source and revision alerts
