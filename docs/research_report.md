# Reproducible ML Research Pipeline for Crypto Price Movement Classification

## 1. Title

Reproducible ML Research Pipeline for Crypto Price Movement Classification.

This document is a research report skeleton for the current MVP. It describes
what is implemented, what is intentionally limited, and which research steps
should come next. It does not claim trading profitability.

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

The MVP supports Binance Spot OHLCV candles and uploaded OHLCV CSV files.

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
splits, walk-forward validation, and rolling out-of-sample windows are planned
research extensions.

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

## 11. Current Reports

The MVP currently creates PNG reports for:

- target distribution;
- metrics comparison;
- CatBoost feature importance.

The run detail page displays report links and renders safe PNG reports inline.

## 12. Known Limitations

Known limitations:

- cryptocurrency market data is noisy and non-stationary;
- short evaluation periods can be misleading;
- high metrics do not imply trading profitability;
- no transaction costs, fees, slippage, or execution constraints are modeled;
- current validation is a single time-based holdout, not walk-forward;
- no stability analysis by symbol, period, regime, or market condition yet;
- no ablation study yet;
- no probability calibration analysis yet;
- no out-of-sample degradation analysis yet.

This MVP should be treated as a research scaffold, not a production forecasting
or trading system.

## 13. Next Research Steps

Planned research steps:

- walk-forward validation;
- stability analysis by symbol and time period;
- ablation study for feature groups;
- additional dummy baseline strategies, such as `prior` and `stratified`;
- probability calibration;
- out-of-sample degradation analysis;
- comparison across intervals and horizons;
- robustness checks around class imbalance;
- clearer reporting of confidence intervals or metric variance across folds.

## 14. How to Reproduce Current MVP Experiment

Run from CSV via CLI:

```powershell
.crypto\Scripts\python.exe manage.py run_csv_pipeline --csv tmp_cli_check/input.csv --symbol BTCUSDT --interval 1h --start-date 2024-01-01 --end-date 2024-01-05 --target-horizon 3
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

Inspect results:

```text
http://127.0.0.1:8000/runs/
http://127.0.0.1:8000/runs/<id>/
```

The run detail page shows metadata, dataset artifacts, model artifacts, metrics,
and generated PNG reports.
