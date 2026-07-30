---
name: implement-slice
description: Implement one small vertical product or research slice from specification through tests, documentation, and verification. Use when the user asks to build a feature or milestone.
argument-hint: <slice name or issue>
disable-model-invocation: true
---
Implement the requested slice: `$ARGUMENTS`.

1. Read `CLAUDE.md`, the product spec, architecture, data contracts, roadmap, and related code.
2. State the user-visible outcome, acceptance criteria, and non-goals.
3. Create `docs/workplans/<slug>.md` if more than two files or one architectural boundary changes.
4. Ask the appropriate subagent to review the plan when data engineering or quantitative methodology is involved.
5. Implement the smallest end-to-end slice.
6. Add unit, integration, and failure-case tests appropriate to the slice.
7. Run narrow tests, then the quality gate.
8. Invoke the reviewer subagent on the diff.
9. Fix high-severity findings.
10. Report exact commands, outcomes, files changed, and unresolved risks.
