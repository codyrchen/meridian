# Meridian Research

Meridian is a research-first platform for studying structural crypto-market events. Its first module, Unlock Lab, builds a point-in-time dataset of token vesting and supply releases, runs event studies, and produces explainable forecasts.

## Start here
1. Read `CLAUDE.md`.
2. Read `docs/product-spec.md` and `docs/roadmap.md`.
3. Run `/implement-slice bootstrap-repository` in Claude Code.
4. Complete the Phase 0 acceptance criteria before ingesting real data.

## Recommended stack
- Python 3.12, uv, FastAPI, Pydantic v2, SQLAlchemy 2, Alembic
- PostgreSQL + TimescaleDB initially; object storage for raw payloads and Parquet
- Polars, DuckDB, statsmodels, scikit-learn, LightGBM/XGBoost only after baselines
- Next.js + TypeScript + TanStack Query/Table + a charting library
- Docker Compose locally; GitHub Actions for CI

## Core principle
The public dashboard is not the moat. The moat is a versioned, auditable dataset and credible empirical research.
