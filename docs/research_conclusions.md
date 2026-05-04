# Research Conclusions

## Research Question

Can simple OHLCV-derived features provide a stable out-of-sample directional
classification signal on real Binance crypto data?

The current answer is cautious: the project now has a reproducible research
workflow for asking that question, but the short frozen smoke benchmark is not
enough to claim a stable predictive edge.

## What Was Built

The project now includes an end-to-end research stack:

- frozen Binance dataset creation with SHA256 manifest;
- real-data EDA for schema, data quality, returns, volatility, and target
  balance;
- time-aware walk-forward benchmark for `dummy`, `baseline`, and `catboost`;
- bootstrap confidence intervals over fold-level metrics;
- regime analysis by volatility and trend buckets;
- error analysis for true positives, true negatives, false positives, false
  negatives, confidence bins, and high-confidence mistakes;
- feature ablation over engineered OHLCV feature groups;
- Forecast Replay / Reality Check for prediction-vs-fact inspection in the
  Django run detail UI.

## Dataset And Reproducibility

The current public real-data reports are generated from the frozen smoke
dataset:

| Field | Value |
| --- | --- |
| Symbol | BTCUSDT |
| Interval | 1h |
| Period | 2025-01-01 to 2025-01-10 |
| Source | Binance Spot OHLCV |
| SHA256 | `cd9cf1076656725deb3118252c3a2c746c856b9136b3f94020e47f92cd34dfde` |

The raw dataset lives in ignored `data/real/`. Public reports and derived CSV/PNG
outputs are reproducible from committed scripts, while the raw real-market data
is not committed.

## Evaluation Protocol

The current benchmark uses:

- target definition:
  `target = 1 if close(t + horizon) > close(t), else 0`;
- target horizon: `3`;
- no random shuffle;
- chronological walk-forward folds;
- train window: `120` rows;
- test window: `24` rows;
- step: `24` rows;
- trainers: `dummy`, `baseline`, `catboost`;
- bootstrap samples: `1000`;
- confidence level: `0.95`.

The smoke run has only `3` folds per model. That keeps the report fast and
reproducible, but it makes uncertainty wide and conclusions deliberately weak.

## Main Findings

- The best trainer by mean F1 in the smoke walk-forward benchmark is
  `baseline`.
- Baseline mean F1 is `0.3757`; mean ROC AUC is `0.6153`.
- Baseline F1 bootstrap CI is `[0.1538, 0.5217]`, which is wide because there
  are only `3` folds.
- Baseline error analysis produced `72` predictions, `39` errors, and an error
  rate of `0.5417`.
- False positives were more common than false negatives: `29` false positives
  vs `10` false negatives.
- Regime metrics varied by volatility and trend buckets; in the smoke run,
  `medium_volatility` had the strongest volatility-bucket F1 (`0.5714`) and
  `downtrend` had the strongest trend-bucket F1 (`0.4906`).
- Feature ablation found `without_moving_average` as the best smoke experiment
  by F1 (`0.5000`), but the delta against all features was small (`0.0065`).

The current evidence says the research workflow is working and exposes model
instability clearly. It does not yet show a robust directional classification
signal.

## What Worked

- The real-data workflow is reproducible from frozen inputs and scripts.
- Time-aware validation avoids random shuffle and makes fold-level behavior
  visible.
- Dummy, LogisticRegression baseline, and CatBoost can be compared under the
  same protocol.
- Confidence intervals, regime analysis, error analysis, and ablation make weak
  spots visible instead of hiding them behind a single metric.
- Forecast Replay makes prediction-vs-fact inspection understandable in the UI.

## What Did Not Work Reliably

- Performance is unstable on the short smoke period.
- The baseline model produced more false positives than false negatives.
- Bootstrap intervals are wide because fold count is small.
- A single short BTCUSDT 1h period is not enough to generalize across symbols,
  intervals, horizons, or market regimes.
- The project does not model transaction costs, fees, slippage, execution, or
  position sizing.
- No current report is evidence of a deployable market edge.

## Error And Regime Insights

The error analysis is the clearest warning layer. In the smoke run, the baseline
model made `39` mistakes out of `72` predictions. The largest visible risk is
false positives: the model often predicted `up` when the realized direction was
`down`.

Regime analysis also shows that performance changes by volatility and trend
labels. These labels are diagnostic, not strategic: they help identify where the
model behaves differently, but they should not be read as a trading rule.

## Feature Ablation Insights

Feature ablation suggests that engineered groups can change outcomes, but the
current smoke result is small and noisy. Removing moving-average features gave
the best F1 in the smoke split, yet the improvement over all features was only
`0.0065`.

This is useful as a prompt for more experiments, not as a final feature
selection decision.

## Forecast Replay / Reality Check

Forecast Replay turns a trained classification model into a small replay table:
predicted direction, realized direction, correctness, probability when
available, and actual price change. It is helpful for inspecting individual
predictions in context.

Forecast Replay is a replay/backtest visualization for classification outputs.
It is not live price forecasting and not a trading signal.

## Limitations

- The current real-data benchmark uses a short smoke dataset.
- Only `BTCUSDT`, `1h`, and one short calendar period are shown in the current
  public results.
- Three folds per model are not enough for strong statistical claims.
- Bootstrap confidence intervals are uncertainty indicators, not proof of model
  superiority.
- Regime thresholds are heuristic.
- Feature ablation currently uses a single chronological split.
- Metrics are directional classification metrics, not profitability metrics.

## Next Research Steps

- Re-run the full research chain on the recommended six-month frozen dataset.
- Compare multiple symbols, intervals, horizons, and calendar periods.
- Add probability calibration and calibration plots.
- Run walk-forward ablation instead of single-split ablation.
- Add more robust regime definitions and sensitivity checks.
- Compare model behavior before and after high-volatility periods.
- Keep Forecast Replay outputs tied to explicit run metadata.

## Linked Reports

- [Real data dataset manifest guide](real_data_dataset_manifest.md)
- [Real data EDA report](real_data_eda.md)
- [Real data walk-forward benchmark](real_data_walk_forward_benchmark.md)
- [Real data regime analysis](real_data_regime_analysis.md)
- [Real data error analysis](real_data_error_analysis.md)
- [Real data feature ablation report](real_data_feature_ablation.md)
- [Model card](model_card.md)
- [Research report](research_report.md)
