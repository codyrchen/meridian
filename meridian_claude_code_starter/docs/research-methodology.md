# Research Methodology

## Primary question
Do token unlock events predict economically and statistically meaningful abnormal returns, volatility, or liquidity changes after accounting for market regime, token characteristics, event type, and tradability?

## Event time
Distinguish:
1. Announcement or schedule-publication date.
2. Contractual vesting date.
3. Effective transferability date.
4. On-chain distribution date.
5. Exchange-deposit or sale proxy date.

The main study begins with contractual/effective unlock dates and later adds observed-flow events.

## Outcomes
- abnormal returns over [-30,-14], [-14,-7], [-7,-1], [0,+1], [0,+7], [0,+14], [0,+30]
- cumulative abnormal return
- realized volatility changes
- volume and turnover changes
- quoted or estimated liquidity-depth changes
- maximum drawdown and recovery time

## Benchmarks
Start with:
- BTC return
- broad crypto market index if point-in-time history is licensed
- category benchmark
- estimated rolling beta model

## Validation
- time-based holdout
- walk-forward evaluation
- grouped splits preventing the same token from dominating both training and test windows
- bootstrapped confidence intervals clustered by token and date where appropriate
- placebo dates
- alternative windows and benchmark definitions
- exclusion sensitivity for low-liquidity and delisted assets

## Bias controls
- survivorship and delisting bias
- look-ahead from revised schedules
- selection bias from only well-documented tokens
- overlapping events
- regime confounding
- stale circulating-supply data
- exchange-volume inflation
- multiple testing

## Modeling order
1. Descriptive distributions.
2. Difference in means and nonparametric tests.
3. OLS / robust regression with interpretable controls.
4. Panel model or mixed effects if justified.
5. Tree-based predictive models.
6. Calibration and decision analysis.

Do not proceed to step 5 until steps 1-4 are stable and documented.
