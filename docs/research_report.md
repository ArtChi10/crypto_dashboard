# Reproducible ML Research Pipeline for Crypto Price Movement Classification

## 1. Title

Reproducible ML Research Pipeline for Crypto Price Movement Classification.

This document is a research report skeleton for the current MVP. It describes
what is implemented, what is intentionally limited, and which research steps
should come next. It does not claim trading profitability.

The companion model card is available at
[`docs/model_card.md`](model_card.md). It summarizes intended use,
out-of-scope use, data, target, metrics, limitations, risks, mitigations, and
reproducibility.

## 2. Problem Statement

The current task is binary classification of short-term cryptocurrency price
movement from OHLCV candles.

For each candle at time `t`, the model tries to classify whether the future
closing price after a fixed horizon is higher than the current closing price.

## 3. Business / Research Goal

The goal is not to build a trading bot. The goal is to build a reproducible ML
research pipeline that can:

- load or ingest OHLCV data;
- create deterministic datasets;
- train baseline and main models;
- evaluate binary classification metrics;
- save datasets, models, metrics, and reports;
- support future research experiments with stronger validation.

The project should make experiments inspectable and repeatable before any
strong claims are made about market predictability.

## 4. Data

The MVP supports Binance Spot OHLCV candles and uploaded OHLCV CSV files. The
repository also includes a small deterministic synthetic sample dataset at
`data/samples/sample_ohlcv.csv` for offline demo and smoke-check reproducibility.

Expected columns:

- `timestamp`;
- `open`;
- `high`;
- `low`;
- `close`;
- `volume`;
- `symbol`.

Supported symbols and intervals depend on Binance Spot API availability. The
current UI and CLI examples use `BTCUSDT` and `1h`, but the pipeline is designed
to accept other valid Binance symbols and candle intervals.

The committed sample dataset is not real market data. It exists so the pipeline
can be exercised without Binance/network access and must not be used for claims
about market predictability or model performance.

A compact EDA report for the committed sample dataset is available at
[`docs/eda_sample_dataset.md`](eda_sample_dataset.md). It documents schema,
missing values, numeric summaries, returns distribution, and target balance
after the current feature/target pipeline.

For real-data benchmarks, the project now uses an ignored frozen dataset flow:
`scripts/freeze_binance_dataset.py` downloads Binance Spot OHLCV candles into
`data/real/` and writes a manifest JSON with request parameters, row count,
timestamp range, missing-value counts, duplicate timestamp count, and SHA256.
The recommended first benchmark is `BTCUSDT`, `1h`, `2025-01-01` to
`2025-07-01`. The manifest guide is
[`docs/real_data_dataset_manifest.md`](real_data_dataset_manifest.md).

The first real-data EDA report is available at
[`docs/real_data_eda.md`](real_data_eda.md). It is generated from a frozen
Binance dataset and summarizes schema/data quality, price and volume behavior,
returns, rolling volatility, and target balance across horizons `1,3,6,12`.

The first real-data walk-forward benchmark is available at
[`docs/real_data_walk_forward_benchmark.md`](real_data_walk_forward_benchmark.md).
It applies the same `DataCleaner -> FeatureBuilder -> TargetBuilder` path to the
frozen dataset, evaluates `dummy`, `baseline`, and `catboost` across sequential
time folds, publishes fold CSV plus summary plots, and estimates bootstrap
confidence intervals over fold-level metrics. On the short smoke dataset, these
intervals are uncertainty indicators, not statistical proof of model
superiority. The benchmark is a stability check for directional classification
metrics, not a trading or profitability claim.

The companion real-data regime analysis is available at
[`docs/real_data_regime_analysis.md`](real_data_regime_analysis.md). It collects
walk-forward test-fold predictions for a selected trainer, labels rows by
volatility and trend regimes, and compares error patterns by regime. This is
diagnostic error analysis, not a strategy.

## 5. Target Definition

The current target is:

```text
target = 1 if close(t + horizon) > close(t), else 0
```

Rows without enough future candles for the selected horizon are removed during
target construction.

## 6. Feature Engineering

The current feature set is built from OHLCV data and includes:

- `return_1`;
- `return_3`;
- `return_6`;
- `return_12`;
- `ma_7`;
- `ma_14`;
- `ema_7`;
- `ema_30`;
- `volatility_7`;
- `volatility_14`;
- `volume_change`;
- `volume_ma_7`;
- `candle_body`;
- `candle_range`.

Feature engineering is currently deterministic and based on each symbol's time
ordered candles.

## 7. Leakage Control

The MVP includes the following leakage controls:

- no random shuffle is used for train/validation/test splitting;
- split is time-based;
- features are designed to use past or current candle values only;
- the future price used to define the target is not kept as a model feature in
  the final dataset;
- `timestamp`, `symbol`, and `target` are excluded from model feature columns;
- only numeric feature columns are used by the trainers.

These controls reduce obvious leakage risk, but they do not replace more robust
time-series validation.

## 8. Current Validation Strategy

The current validation strategy is a single global time-based holdout split:

- train: 70%;
- validation: 15%;
- test: 15%.

Rows are sorted by `timestamp`, and the split preserves chronological order.

The current split is global by timestamp across the final dataset. Per-symbol
splits and rolling out-of-sample windows are planned research extensions.

`WalkForwardValidationService` is now available as an independent research
utility for building row-count based walk-forward folds. It creates chronological
train/test windows without shuffle.

`WalkForwardEvaluationService` is also available as a standalone research
utility. It trains a supplied trainer on each fold, evaluates metrics through
`Evaluator`, and returns a fold-level `DataFrame`. It is not yet integrated into
the main pipeline, persistence layer, UI, or reports.

## 9. Models

The MVP currently trains:

- DummyClassifier naive baseline with `strategy="most_frequent"`;
- LogisticRegression baseline through an sklearn `Pipeline` with
  `StandardScaler`;
- CatBoostClassifier as the main model.

LogisticRegression and CatBoost require at least two classes in `y_train`.
DummyClassifier intentionally allows one-class `y_train`, because it is a naive
research baseline.

## 10. Metrics

The current evaluator computes:

- accuracy;
- precision;
- recall;
- f1;
- roc_auc;
- confusion matrix.

If probability scores are unavailable, `roc_auc` is reported as `None`. If
`y_true` contains only one class, `roc_auc` is also reported as `None`.

The evaluation layer also includes `PeriodStabilityAnalysisService`, which
analyzes existing test predictions by daily, weekly, or any pandas frequency
period. It returns per-period rows with class balance and classification metrics.

The evaluation layer also includes:

- `WalkForwardValidationService`, which builds sequential walk-forward folds;
- `WalkForwardEvaluationService`, which trains and evaluates a supplied trainer
  fold by fold and records fold errors without stopping the whole run by
  default;
- `FeatureAblationService`, which compares metrics for all available features
  against experiments that remove predefined feature groups.
- `ForecastReplayService`, which builds a replay/reality-check table from
  history candles, future candles, an already trained classification model, and
  selected feature columns.

The CLI command `run_research_evaluation` can run walk-forward evaluation and
feature ablation on an existing final parquet/csv dataset and save CSV outputs
without creating Django metadata.

Forecast Replay is now available as an optional Binance UI flow. When enabled,
the Binance pipeline downloads a future candle window after `end_date`, uses the
trained model selected in `catboost -> baseline -> dummy` order, and saves a
replay table plus PNG report as persisted `ReportArtifact` records. Its purpose
is replay/backtest visualization of classification decisions, not live price
forecasting. The replay table includes direction labels, correctness labels,
actual price change, and actual percentage change so the run detail page can
show a compact reality-check summary.

## 11. Current Reports

The MVP currently creates PNG reports for:

- target distribution;
- metrics comparison;
- CatBoost feature importance;
- period stability table as CSV;
- period stability plot as PNG;
- forecast replay table as CSV;
- forecast replay plot as PNG.

The run detail page displays report links, renders safe PNG reports inline, and
shows a Forecast Replay preview block with correct/total, hit rate, average
probability when available, and the first replay rows from the CSV.

## Current Reproducible Experiment

A recorded sample experiment is available at
[`docs/experiment_summary_sample.md`](experiment_summary_sample.md). It uses the
committed deterministic synthetic dataset, records the exact CSV pipeline
command, and summarizes generated artifacts, dummy/baseline/CatBoost metrics,
confusion matrices, and period stability output.

This sample experiment is a reproducibility and pipeline sanity check only. It
does not provide evidence of real market predictability.

A real-data benchmark should start by freezing the Binance dataset and checking
its manifest, then reviewing the real-data EDA report, then running the
walk-forward benchmark before ablation, stability, or Forecast Replay
experiments. The frozen input, EDA, and fold-by-fold benchmark improve
reproducibility, but they still do not make metrics evidence of trading
profitability.

## 12. Known Limitations

Known limitations:

- cryptocurrency market data is noisy and non-stationary;
- short evaluation periods can be misleading;
- high metrics do not imply trading profitability;
- no transaction costs, fees, slippage, or execution constraints are modeled;
- the main pipeline still uses a single time-based holdout;
- walk-forward fold generation and fold-by-fold evaluation exist only as
  standalone research utilities;
- walk-forward persistence, UI, and report integration are not implemented yet;
- feature ablation exists as a standalone research utility, but ablation reports
  and pipeline integration are not implemented yet;
- forecast replay is integrated with the Binance UI and run detail preview, but
  it remains a simplified synchronous replay/backtest visualization;
- period stability is currently based on the single holdout test segment, not on
  rolling walk-forward windows;
- no stability analysis by symbol, regime, or market condition yet;
- no automated ablation artifact/report generation yet;
- no probability calibration analysis yet;
- no out-of-sample degradation analysis yet.

This MVP should be treated as a research scaffold, not a production forecasting
or trading system.

## 13. Next Research Steps

Planned research steps:

- integrate walk-forward evaluation with reporting and experiment persistence;
- stability analysis by symbol and market regime;
- integrate feature ablation with reporting and experiment persistence;
- extend Forecast Replay with richer UI controls and more detailed replay
  diagnostics;
- additional dummy baseline strategies, such as `prior` and `stratified`;
- probability calibration;
- out-of-sample degradation analysis;
- comparison across intervals and horizons;
- robustness checks around class imbalance;
- clearer reporting of confidence intervals or metric variance across folds.

## 14. How to Reproduce Current MVP Experiment

Run from CSV via CLI:

```powershell
.crypto\Scripts\python.exe manage.py run_csv_pipeline --csv data/samples/sample_ohlcv.csv --symbol BTCUSDT --interval 1h --start-date 2024-01-01 --end-date 2024-01-10 --target-horizon 3
```

Run from Binance via CLI:

```powershell
.crypto\Scripts\python.exe manage.py run_binance_pipeline --symbol BTCUSDT --interval 1h --start-date 2024-01-01 --end-date 2024-01-10 --target-horizon 3 --skip-catboost
```

Run from Binance via UI:

```text
http://127.0.0.1:8000/binance/
```

Run from uploaded CSV via UI:

```text
http://127.0.0.1:8000/upload/
```

Run offline research checks on an existing final dataset:

```powershell
.crypto\Scripts\python.exe manage.py run_research_evaluation --dataset tmp_research_check/final.parquet --output-dir tmp_research_check/out --trainer dummy --run-walk-forward --run-ablation --train-window 40 --test-window 20
```

Supported research CLI trainers are `dummy`, `baseline`, and `catboost`.
CatBoost uses lighter research defaults in this command, but it can still be
slower than the simpler trainers. Fold-level one-class training failures are
recorded as `error_message` rows by the evaluation services instead of weakening
trainer validation.

Regenerate the real-data walk-forward benchmark from a frozen raw dataset and
manifest:

```powershell
.crypto\Scripts\python.exe scripts\run_real_data_walk_forward_benchmark.py --dataset data\real\binance_BTCUSDT_1h_2025-01-01_2025-01-10.parquet --manifest data\real\binance_BTCUSDT_1h_2025-01-01_2025-01-10.manifest.json --output-doc docs\real_data_walk_forward_benchmark.md --output-dir docs\assets\real_data_walk_forward --target-horizon 3 --train-window 120 --test-window 24 --step 24 --trainers dummy,baseline,catboost --bootstrap-samples 1000 --confidence-level 0.95 --random-state 42
```

Regenerate the real-data regime analysis:

```powershell
.crypto\Scripts\python.exe scripts\run_real_data_regime_analysis.py --dataset data\real\binance_BTCUSDT_1h_2025-01-01_2025-01-10.parquet --manifest data\real\binance_BTCUSDT_1h_2025-01-01_2025-01-10.manifest.json --output-doc docs\real_data_regime_analysis.md --output-dir docs\assets\real_data_regime_analysis --trainer baseline --target-horizon 3 --train-window 120 --test-window 24 --step 24 --trend-window 24 --trend-threshold 0.01
```

Inspect results:

```text
http://127.0.0.1:8000/runs/
http://127.0.0.1:8000/runs/<id>/
```

The run detail page shows metadata, dataset artifacts, model artifacts, metrics,
and generated PNG reports.
