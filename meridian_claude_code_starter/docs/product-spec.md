# Product Specification

## Product thesis
Crypto investors can see that a token unlock is scheduled, but often cannot answer: what becomes transferable, who receives it, whether it reaches liquid venues, what comparable events did, and how much of the effect was already priced.

## Primary user
An investment analyst or quant researcher who needs to evaluate upcoming supply events and defend the conclusion to a portfolio manager.

## Initial job to be done
"For an upcoming unlock, show the verified schedule, economic size, recipient class, liquidity context, historical analogs, expected abnormal-return distribution, and the evidence behind every number."

## MVP scope
- 25-50 manually verified tokens
- Daily market data
- Canonical unlock-event schema
- Raw source archive and lineage
- Event-study engine
- Historical event explorer
- Upcoming unlock table
- Token detail page
- Reproducible research report

## Explicit non-goals for MVP
- Trading execution
- Wallet deanonymization
- Real-time tick data
- Fully automated PDF tokenomics extraction
- AI-generated investment recommendations
- Portfolio management or personalized financial advice

## User stories
1. As a researcher, I can inspect the source and revision history for each unlock.
2. As a researcher, I can compare unlock size against circulating supply, ADV, and liquidity.
3. As a quant, I can rerun event studies with configurable windows and benchmarks.
4. As an investor, I can see upcoming events ranked by estimated materiality.
5. As a reviewer, I can reproduce every chart from a committed research specification.

## MVP acceptance criteria
- At least 95% of canonical unlock fields are complete for the curated universe.
- Duplicate-event and impossible-supply checks run automatically.
- Every canonical event links to at least one source artifact.
- Event study supports market-adjusted and beta-adjusted returns.
- Results can be rebuilt from a clean clone with documented commands.
- Dashboard never displays a prediction without model version, timestamp, and uncertainty.
