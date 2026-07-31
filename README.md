# Meridian Research

Meridian is a research-first platform for studying structural crypto-market
events. Its first module, Unlock Lab, builds a point-in-time dataset of token
vesting and supply releases, runs event studies, and produces explainable
forecasts.

Epic 0 (implemented) is the smallest end-to-end vertical slice: one manually
verified ARB unlock event, daily ARB and BTC prices, and a reproducible
[-30, +30]-day event study producing a 61-row table, a chart, and a run
manifest.

## Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) (`curl -LsSf https://astral.sh/uv/install.sh | sh`)
- Docker (Desktop or OrbStack) for PostgreSQL 16 — only needed for the
  database-backed pipeline; fixture mode runs without it
- Optional: a free CoinGecko demo API key for live ingestion

## Setup

```bash
make bootstrap          # uv sync: installs the workspace and dev tools
cp .env.example .env    # then fill in COINGECKO_API_KEY (optional)
```

## Run the full pipeline (requires Docker)

```bash
make db-up              # start PostgreSQL 16 and wait until healthy
make migrate            # alembic upgrade head
make seed-event         # load the curated ARB unlock + archived source artifact
make ingest             # daily ARB + BTC bars from CoinGecko (idempotent)
make report             # [-30,+30] event study -> outputs/<run_id>/
```

`make report` writes to `outputs/<run_id>/`:

- `event_study.csv` — 61 rows (offset day -30..+30): date, closes, daily log
  returns, raw cumulative ARB log return, abnormal return
  (`ARB_log_return_t - BTC_log_return_t`), and CAR (cumulative abnormal
  return).
- `car_chart.png` — CAR and raw cumulative return with day 0 marked.
- `run_manifest.json` — code SHA, config hash, data-snapshot checksums,
  package versions, window, methodology.

## Reproducible fixture mode (no network, no database)

```bash
make report-fixture     # deterministic: identical CSV bytes on every run
```

## Tests and quality gate

```bash
make test               # unit tests only (no network, no database)
make db-up && make test-integration   # migration roundtrip + e2e pipeline
make gate               # ruff check + format check + mypy + full pytest
```

Integration tests skip with an explanatory message when PostgreSQL is
unreachable. Frontend gates run only once `apps/web` exists (see
`docs/decision-log.md`).

## Repository layout

```text
packages/domain       pure domain models and invariants (no I/O)
packages/connectors   CoinGecko client + immutable checksum archive
packages/pipelines    DB tables, ingestion, DQ checks, curated-event loader, CLI
packages/research     event-study windows, returns/CAR, report artifacts
migrations/           Alembic migrations
config/slice.yaml     Epic 0 configuration (asset, benchmark, window)
data/curated/         verified unlock event YAML + archived primary sources
data/raw/             local immutable payload archive (gitignored)
outputs/              run artifacts (gitignored)
docs/                 specification, contracts, methodology, decision log
```

## Data and reproducibility principles

- Raw payloads are archived immutably with source, retrieval timestamp,
  checksum, and license class; normalized rows keep lineage via
  `source_artifact_id` and `knowledge_timestamp`.
- Missing observations fail loudly; nothing is interpolated or silently
  imputed.
- Verified facts are distinguished from derived values in
  `data/curated/unlock_events/arb.yaml`.
- Real API payloads and credentials are never committed; fixtures in git are
  synthetic.

## Start here (contributors)

1. Read `CLAUDE.md`.
2. Read `docs/product-spec.md`, `docs/roadmap.md`, and
   `docs/workplans/epic-0-vertical-slice.md`.
3. Run the fixture-mode report and the unit tests before touching code.

## Recommended stack (later phases)

- FastAPI for `apps/api`; Next.js + TypeScript for `apps/web` (Phase 4)
- Object storage for raw payloads and Parquet; DuckDB for local analytics
- statsmodels / scikit-learn / gradient boosting only after interpretable
  baselines (see `docs/research-methodology.md`)

## Core principle

The public dashboard is not the moat. The moat is a versioned, auditable
dataset and credible empirical research.
