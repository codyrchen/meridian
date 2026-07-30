---
name: research-audit
description: Audit a research result, notebook, model, or proposed signal for leakage, bias, weak validation, unsupported claims, and reproducibility.
argument-hint: <path or research question>
disable-model-invocation: true
---
Audit `$ARGUMENTS`.

Produce:
1. Claimed estimand and hypothesis.
2. Data availability and point-in-time audit.
3. Sample-construction and missingness audit.
4. Leakage, survivorship, overlap, and multiple-testing review.
5. Benchmark and validation review.
6. Reproduction commands and whether they succeed.
7. Findings ranked critical/high/medium/low.
8. Required changes before publication.
Do not rewrite the research until the audit is complete.
