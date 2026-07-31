# Roadmap

## Phase 0 - Repository and guardrails (2-3 days)
- Monorepo scaffold, task runner, local services, CI, secrets template, logging, test fixtures.
- Acceptance: one command boots services; quality gate passes; sample health endpoint works.

## Phase 1 - Canonical data model (4-7 days)
- Asset, protocol, source artifact, schedule, event, and market-bar schemas.
- Acceptance: migrations, factories, invariants, lineage demo.

## Phase 2 - Curated unlock dataset (1-2 weeks)
- Manually verify 25 tokens and archive sources.
- Acceptance: coverage dashboard and zero unresolved blocking DQ errors.

## Phase 3 - Market data and event-study engine (1-2 weeks)
- Daily prices, benchmark returns, configurable event windows.
- Acceptance: reproducible notebook/report and placebo tests.

## Phase 4 - Product MVP (1-2 weeks)
- API, upcoming-events table, event explorer, token page, source drawer.
- Acceptance: end-to-end browser flow and integration tests.

## Phase 5 - Research-grade expansion (3-6 weeks)
- 100-200 tokens, liquidity features, regime labels, model baselines, published paper.

## Phase 6 - Platform expansion
- Treasury flows, observed distributions, governance, developer activity, research assistant.
