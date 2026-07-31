---
paths:
  - "**/*.py"
---
- Use Python 3.12 syntax and type all public interfaces.
- Use UTC-aware datetimes.
- Use Pydantic for boundaries and dataclasses/domain types internally when appropriate.
- No network calls in unit tests; use recorded or synthetic fixtures.
- Connector tests must cover pagination, rate limiting, malformed payloads, and retry exhaustion.
- Research functions must accept explicit data snapshots and configuration; no hidden globals.
