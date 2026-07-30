# Decision Log

Use one entry per material decision.

## Template
- Date:
- Decision:
- Context:
- Alternatives considered:
- Why this choice:
- Consequences:
- Revisit trigger:

## Initial decisions
### Monorepo before microservices
Use a modular monolith with clear package boundaries. Revisit only after operational evidence shows independent scaling or ownership needs.

### Curated dataset before automated extraction
Build a small high-confidence dataset first. Automation without a gold set creates invisible errors.

### Daily data before intraday data
Daily observations are sufficient to test the core hypothesis and are easier to license, validate, and reproduce.
