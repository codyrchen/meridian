# Workplan: Epic 0 — Smallest end-to-end vertical slice

Status: approved 2026-07-30. One token (ARB), one verified unlock event, daily
prices for ARB + BTC, a [-30, +30] event window, one reproducible table, one
chart, tests, and documented local commands.

## Outcome

From a clean clone a developer can:

1. Boot PostgreSQL 16 (Docker Compose) and run Alembic migrations.
2. Load one manually verified ARB unlock event with an archived, checksummed
   source artifact.
3. Ingest daily ARB and BTC market data from CoinGecko idempotently, with raw
   payloads archived immutably and lineage preserved.
4. Compute daily log returns, raw cumulative log return, and BTC-adjusted
   cumulative abnormal return (CAR) over event days [-30, +30].
5. Produce `event_study.csv` (61 rows), `car_chart.png` (day 0 marked), and
   `run_manifest.json` in `outputs/<run_id>/`.
6. Reproduce a byte-deterministic fixture-mode report with no network and no
   database (`make report-fixture`).
7. Pass lint, format, type check, migration roundtrip, unit, and integration
   tests with documented commands.

## Non-goals

No frontend, public API, authentication, cloud infrastructure, scheduler,
AI assistant, prediction models, additional tokens, beta-adjusted returns,
factor models, hypothesis tests, TimescaleDB, or automated unlock extraction.

## Approved decisions

- Repository flattened; starter contents live at the repo root.
- Asset: ARB. Candidate event: the June 2026 scheduled monthly investor/team
  unlock. Exact timestamp, quantity, allocation, and supply percentages must
  be verified against an official Arbitrum source or the on-chain vesting
  contract before the curated record is created; the primary source is
  archived with retrieval timestamp and checksum; verified facts are
  distinguished from derived values; aggregators are secondary cross-checks
  only. If the event cannot be sufficiently verified, stop and report.
- Returns: `abnormal_return_t = ARB_log_return_t - BTC_log_return_t`;
  CAR is the cumulative sum of abnormal returns; also report the raw
  cumulative ARB log return.
- PostgreSQL 16 via Docker Compose; no TimescaleDB.
- uv workspace; Makefile task runner; SQLAlchemy 2; Alembic; Pydantic v2.
- Daily UTC data; day 0 = UTC calendar date of the unlock; window [-30, +30];
  a price on day -31 is required so the day -30 return is computable.
- Fail loudly on missing required observations; no interpolation or silent
  imputation.
- Local raw artifact storage using `file://` URIs under `data/raw/`
  (gitignored). Synthetic fixtures only in git; real API payloads and
  credentials stay uncommitted.
- `source_confidence` vocabulary: `verified_primary | verified_secondary |
  unverified`.
- `run_manifest.json` instead of a `research_run` table for Epic 0.
- SQL schema is the canonical naming baseline, corrected where CLAUDE.md
  requires: `quote_currency` added to `market_bar_daily`, enum CHECK
  constraints added, supply-percentage fields stay nullable,
  `docs/data-contracts.md` updated to match the implemented schema.
- Frontend quality gates run only when `apps/web` exists.
- Guard script uses `python3`.

## Repository structure (Epic 0 files)

```text
meridian/
  CLAUDE.md  README.md  Makefile  pyproject.toml  uv.lock
  docker-compose.yml  .env.example  alembic.ini  .gitignore
  .claude/  scripts/claude_pretool_guard.sh
  docs/ (existing) + docs/workplans/epic-0-vertical-slice.md
  migrations/env.py  migrations/versions/0001_initial.py
  config/slice.yaml
  data/curated/unlock_events/arb.yaml
  data/raw/                      # gitignored payload archive
  packages/
    domain/src/meridian_domain/{enums.py, models.py}
    connectors/src/meridian_connectors/{archive.py, coingecko.py}
    pipelines/src/meridian_pipelines/{db.py, tables.py, load_unlock_event.py,
                                      ingest_market_data.py, dq_checks.py,
                                      cli.py}
    research/src/meridian_research/{windows.py, event_study.py, report.py}
  outputs/                       # gitignored run artifacts
  tests/{fixtures/, unit tests, integration/}
```

Architecture boundaries: `domain` has no I/O; `connectors` never touch the
database; `pipelines` orchestrate; `research` is pure computation over
explicitly passed data.

## Database tables (Alembic 0001)

- `source_artifact` — as drafted in `sql/initial_schema.sql`; `object_uri`
  holds `file://` paths locally; `UNIQUE (source_name, checksum_sha256)`.
- `asset` — as drafted.
- `unlock_event` — adds CHECK constraints for `release_type`,
  `allocation_bucket`, `source_confidence`; supply percentages nullable.
- `market_bar_daily` — adds `quote_currency TEXT NOT NULL DEFAULT 'usd'`;
  primary key `(asset_id, ts, source_artifact_id)`; corrections are
  append-only new lineage rows; readers select the row with the latest
  `knowledge_timestamp` per `(asset_id, ts)`.

Deferred: `protocol`, `vesting_schedule`, `liquidity_snapshot`,
`lineage_edge`, `research_run`, `model_version`.

## Data sources

- CoinGecko `GET /api/v3/coins/{id}/market_chart/range` (daily price, volume,
  market cap; demo API key via `COINGECKO_API_KEY` in `.env`; free-tier
  history cap ~365 days). The endpoint returns daily price points, not OHLC,
  so `close` is populated and `open/high/low` stay NULL.
- Unlock event: manual curation from official Arbitrum Foundation
  documentation (archived as a `source_artifact`), cross-checked against an
  aggregator as secondary evidence only.

## Tests

1. Migration upgrade → downgrade → upgrade roundtrip (integration).
2. Domain model validation incl. failure cases (negative amounts, naive
   datetimes, bad enum values).
3. CoinGecko parser: fixture payload, malformed payload, empty response,
   duplicate timestamps.
4. CoinGecko client: 429 backoff, bounded retry exhaustion, range chunking
   (mocked transport; no network).
5. Archive: checksum correctness; identical payload dedupes; never
   overwrites.
6. Ingestion idempotency: run twice, no duplicate bars, lineage intact
   (integration).
7. DQ checks: negative price fails, duplicate event fails, missing window
   coverage fails.
8. Event study: hand-computed CAR on a synthetic path matches exactly;
   UTC day-0 convention; missing-day policy raises; benchmark alignment.
9. Report determinism: fixture mode produces a byte-identical CSV across
   runs.
10. CLI smoke test end-to-end against the test database (integration).

Unit tests use synthetic fixtures only and never touch the network.
Integration tests skip with a clear message when the database is
unreachable, and must pass before Epic 0 is declared done.

## Acceptance criteria

1. `make bootstrap && make db-up && make migrate && make seed-event &&
   make ingest && make report` succeed from a clean clone and are documented
   in the README with expected outputs.
2. `outputs/<run_id>/` contains `event_study.csv` (61 rows: offset day, date,
   closes, log returns, raw cumulative log return, abnormal return, CAR),
   `car_chart.png` (CAR and raw cumulative return with day 0 marked), and
   `run_manifest.json` (code SHA, config hash, data snapshot summary,
   package versions, generated-at).
3. The unlock event links to a `source_artifact` with checksum and retrieval
   timestamp; every market bar carries `source_artifact_id` and
   `knowledge_timestamp`.
4. Re-running `make ingest` changes nothing; DQ checks block bad data.
5. `make report-fixture` is byte-deterministic for the CSV, offline, DB-free.
6. `uv run ruff check .`, `uv run ruff format --check .`,
   `uv run mypy packages`, `uv run pytest -q` all pass. Frontend gates are
   skipped while `apps/web` does not exist.
7. No real API payloads, keys, or `.env` in git.

## Execution order

1. Flatten repo; fix guard script; write this workplan; append decision log.
2. Scaffold uv workspace, Makefile, tool config, Docker Compose, `.env.example`.
3. Domain models + unit tests.
4. SQLAlchemy tables + Alembic 0001 + migration roundtrip test.
5. Archive + CoinGecko connector + unit tests.
6. Unlock loader + ingestion + DQ checks + CLI + tests.
7. Event study + report + determinism tests.
8. Fixture-mode end-to-end + integration smoke test.
9. Verify and curate the ARB event (archive primary source; stop if
   unverifiable).
10. Real run against Postgres + live CoinGecko (requires Docker runtime).
11. Update `docs/data-contracts.md`, README; run the full quality gate;
    report results.

## Known environment risks

- No container runtime was present at approval time; the user installs
  Docker Desktop/OrbStack out of band. DB-dependent verification runs as
  soon as it is available.
- CoinGecko free tier may throttle or require a demo key; ingestion retries
  are bounded and failures are reported, never silently retried.
