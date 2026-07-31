# Architecture

## Logical flow
Sources -> immutable raw zone -> normalization -> canonical warehouse -> research marts -> model registry -> API -> web product.

## Suggested monorepo
```text
apps/
  api/
  web/
  worker/
packages/
  domain/
  connectors/
  pipelines/
  research/
  models/
  observability/
infra/
  docker/
  terraform/
  github/
docs/
  workplans/
notebooks/
  exploratory/
  published/
sql/
tests/
```

## Storage
- PostgreSQL: metadata, entities, schedules, events, lineage, model metadata.
- TimescaleDB or partitioned Postgres: daily/hourly market series.
- Object storage: immutable raw responses, source documents, Parquet snapshots, model artifacts.
- DuckDB: local analytical execution over Parquet.

## Service boundaries
- Ingestion worker: schedules connectors and records raw payloads.
- Normalizer: maps source records into canonical entities with validation.
- Research runner: executes versioned specifications and publishes artifacts.
- Model service: loads approved models and returns predictions with provenance.
- API: read-oriented product interface.

## Initial deployment
Use one repository, one Postgres instance, one object bucket, one API service, one web service, and one scheduled worker. Do not introduce Kafka, Kubernetes, microservices, or a feature store during MVP.
