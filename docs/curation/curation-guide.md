# Manual Event-Curation Guide

How to produce one verified unlock event for the Meridian canonical dataset.
The curator (a human) completes a template-v2 file; Claude/the pipeline may
only ingest files whose mechanical validation passes and whose
`curation.status` is `ready`. Nothing in this workflow parses documents
automatically — reading and judgment are the curator's job; the machine only
re-checks structure, taxonomy, checksums, and provenance rules.

## Workflow (per event)

1. **Identify the candidate.** Token, approximate date, allocation. Confirm it
   is a discrete scheduled unlock (not continuous emission, not the TGE day).
2. **Find primary sources.** Official team/foundation documentation, blog,
   governance post, tokenomics page — or the on-chain vesting contract. An
   aggregator is never a primary source.
3. **Archive before you cite.** For every primary/on-chain source:
   - save the exact bytes you read (browser "save page", curl, PDF download);
   - compute the checksum: `shasum -a 256 <file>`;
   - move the file to `data/raw/<source_name>/<sha256>.raw` (gitignored
     default). Only if the license explicitly permits redistribution may it
     live in `data/curated/sources/<source_name>/<sha256>.raw` with
     `redistributable: true`.
4. **Copy the template** `docs/curation/event-template.yaml` to
   `data/curated/unlock_events/<token>/<YYYY-MM-DD>_<bucket>.yaml` and fill it:
   - record each source with its role, the claims it supports, and the exact
     supporting excerpt/locator;
   - `reported` amounts must appear verbatim in a primary source;
   - `derived` amounts require the full formula and which source verifies each
     input;
   - unknown values stay `null` — never estimate into a canonical field;
   - combined tranches the primary source does not split: bucket `unknown`
     plus `bucket_composition` (aggregator splits go there, marked
     `secondary_cross_check`, never into `allocation_bucket`).
5. **Cross-check.** Consult at least one independent secondary source; record
   what it reports and whether it agrees. Disagreement blocks the file:
   resolve it or move the candidate to `data/curated/exclusions.yaml`.
6. **Self-check, then validate mechanically:**
   ```
   make validate-curation FILE=data/curated/unlock_events/<token>/<file>.yaml
   ```
   Fix everything it reports.
7. **Mark ready.** Set every checklist item to `true` and
   `curation.status: ready`. Commit the YAML (and the archived snapshot only
   when redistributable).
8. **Rejected candidates** go to `data/curated/exclusions.yaml`
   (see `docs/curation/exclusions-template.yaml`) — every considered-but-
   excluded event is recorded with a reason. Silent skipping is forbidden.

## Allocation-bucket mapping rules

| Bucket | Maps from (source vocabulary) |
|---|---|
| `team` | core team, founders, employees, advisors, employed contributors |
| `investor` | seed/private/strategic rounds, VCs, SAFT holders |
| `foundation` | foundation/association entities holding for operations |
| `treasury` | DAO/protocol treasury under governance control |
| `ecosystem` | ecosystem growth funds, grants, partnerships |
| `community` | community allocations incl. public sale, not otherwise classified |
| `airdrop` | retroactive/claim-based distributions |
| `rewards` | liquidity mining, staking incentives, launchpool programs |
| `unknown` | source does not identify the recipient class (or unsplit combined tranche) |

## Vesting series

Tranches of one schedule share a `vesting_series` section with a stable
`series_slug` (e.g. `arb-team-investor-monthly`). Give the event its 1-based
`tranche_number`. This is how later analysis knows monthly observations of the
same schedule are not independent.

## Event-kind discipline

`scheduled` records what a schedule says will unlock. Observed on-chain
transfers or exchange deposits are separate events (`observed_transfer`,
`observed_exchange_deposit`) with their own sources — never merged into the
scheduled record.

## What the machine enforces (so you don't have to remember)

`make validate-curation` rejects: missing/malformed sections or unknown
fields; missing primary source; schedule/amount claims not backed by a
primary or on-chain source; unarchived primary sources; checksum mismatches;
`derived` without a derivation; secondary checks without `reports`/`agrees`;
any `agrees: false`; `ready` status with an unchecked checklist item;
`tranche_number` without a series; naive (timezone-less) timestamps.

## What validation cannot check

Whether the excerpt really says what you claim, whether the source is really
primary, and whether the derivation is economically sensible. That judgment
is the curation. When in doubt: exclude, record why, move on.
