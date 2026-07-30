-- Initial conceptual schema; convert to Alembic migrations during implementation.
CREATE TABLE source_artifact (
  id UUID PRIMARY KEY,
  source_name TEXT NOT NULL,
  source_uri TEXT,
  retrieved_at TIMESTAMPTZ NOT NULL,
  knowledge_timestamp TIMESTAMPTZ NOT NULL,
  checksum_sha256 TEXT NOT NULL,
  license_class TEXT NOT NULL,
  object_uri TEXT NOT NULL,
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  UNIQUE (source_name, checksum_sha256)
);

CREATE TABLE asset (
  id UUID PRIMARY KEY,
  symbol TEXT NOT NULL,
  name TEXT NOT NULL,
  chain_id TEXT,
  contract_address TEXT,
  decimals INTEGER,
  coingecko_id TEXT,
  valid_from TIMESTAMPTZ NOT NULL,
  valid_to TIMESTAMPTZ,
  UNIQUE (chain_id, contract_address, valid_from)
);

CREATE TABLE unlock_event (
  id UUID PRIMARY KEY,
  asset_id UUID NOT NULL REFERENCES asset(id),
  scheduled_at TIMESTAMPTZ NOT NULL,
  transferable_at TIMESTAMPTZ,
  release_type TEXT NOT NULL,
  allocation_bucket TEXT NOT NULL,
  amount_tokens NUMERIC(50,18) NOT NULL,
  percent_current_circulating NUMERIC(20,10),
  percent_total_supply NUMERIC(20,10),
  source_artifact_id UUID NOT NULL REFERENCES source_artifact(id),
  source_confidence TEXT NOT NULL,
  knowledge_timestamp TIMESTAMPTZ NOT NULL,
  valid_from TIMESTAMPTZ NOT NULL,
  valid_to TIMESTAMPTZ,
  ambiguity_flags JSONB NOT NULL DEFAULT '[]'::jsonb
);

CREATE TABLE market_bar_daily (
  asset_id UUID NOT NULL REFERENCES asset(id),
  ts DATE NOT NULL,
  open NUMERIC(30,12),
  high NUMERIC(30,12),
  low NUMERIC(30,12),
  close NUMERIC(30,12),
  volume_usd NUMERIC(40,8),
  market_cap_usd NUMERIC(40,8),
  source_artifact_id UUID NOT NULL REFERENCES source_artifact(id),
  knowledge_timestamp TIMESTAMPTZ NOT NULL,
  PRIMARY KEY (asset_id, ts, source_artifact_id)
);
