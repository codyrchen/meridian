# Claude Code Prompt Library

## Bootstrap
"Read CLAUDE.md and all docs. Do not implement yet. Explore the empty/scaffold repository and propose the smallest Phase 0 plan that gives us a reproducible Python + Next.js monorepo, Postgres, CI, and one end-to-end health check. Include files, commands, acceptance tests, and non-goals."

## Data-model slice
"Use /implement-slice to add source_artifact, asset, and unlock_event domain models plus migrations. Enforce point-in-time fields and immutable raw lineage. Use synthetic fixtures only."

## Connector slice
"Implement a CoinGecko daily market-data connector behind the connector interface. Handle pagination/rate limits/retries, archive raw responses, normalize to canonical bars, and test with fixtures. Do not add another source."

## Research slice
"Ask the quant-researcher subagent to design a minimal event study for daily returns. Then implement only market-adjusted CAR with configurable windows, missing-coverage rules, and placebo tests. Produce a deterministic fixture report."

## Review
"Invoke the reviewer subagent on the current diff. Focus on hidden look-ahead, destructive migrations, source-field leakage, silent data cleaning, secrets, and tests that assert implementation rather than behavior."

## Session reset
"Read the latest workplan and git diff. Summarize current state, what is verified, what is unverified, and the next smallest acceptance criterion. Do not make changes."
