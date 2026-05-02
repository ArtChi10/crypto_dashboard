# Model Card: Crypto OHLCV Price Movement Classification Pipeline

## 1. Model / System Name

Crypto OHLCV Price Movement Classification Pipeline.

This model card describes the current MVP pipeline as a research system. It
covers the implemented trainers, data assumptions, evaluation outputs,
limitations, risks, and reproducibility notes.

## 2. Model Type

The pipeline currently supports three model families:

- `DummyClassifier` naive baseline;
- `LogisticRegression` baseline with `StandardScaler`;
- `CatBoostClassifier` main model.

The dummy model is included as a minimal reference point. The LogisticRegression
model provides a simple linear baseline. CatBoost is the current non-linear main
model.

## 3. Intended Use

Intended uses:

- offline ML research on OHLCV datasets;
- reproducible experimentation with local artifacts and metadata;
- pipeline demonstration for binary classification on time-ordered market-like
  tabular data;
- sanity checks around data preparation, feature generation, target creation,
  model training, metrics, and reports.

The system is designed to help inspect an ML workflow. It is not designed to
make financial decisions.

## 4. Out-of-Scope Use

Out-of-scope uses:

- live trading;
- financial advice;
- automated order execution;
- position sizing or portfolio allocation;
- profitability prediction;
- production trading or monitoring.

Outputs should not be interpreted as trading signals.

## 5. Data

Expected input schema:

- `timestamp`;
- `open`;
- `high`;
- `low`;
- `close`;
- `volume`;
- `symbol`.

Supported data sources:

- uploaded CSV files;
- Binance Spot OHLCV candles through REST API;
- committed deterministic synthetic sample dataset for offline demo and smoke
  checks.

The committed sample dataset is located at:

```text
data/samples/sample_ohlcv.csv
```

The sample dataset is not real market data. It exists to make the pipeline easy
to run without network access.

## 6. Target

The current binary target is:

```text
target = 1 if close(t + horizon) > close(t), else 0
```

Rows without enough future candles for the selected horizon are removed during
target construction. The default examples use `horizon=3`.

## 7. Features

Feature groups currently include:

- raw OHLCV fields: `open`, `high`, `low`, `close`, `volume`;
- returns: `return_1`, `return_3`, `return_6`, `return_12`;
- moving averages: `ma_7`, `ma_14`, `ema_7`, `ema_30`;
- volatility: `volatility_7`, `volatility_14`;
- volume features: `volume_change`, `volume_ma_7`;
- candle shape: `candle_body`, `candle_range`.

Trainers exclude `timestamp`, `symbol`, and `target` from model feature columns
and use numeric columns only.

## 8. Training / Validation

Current main pipeline behavior:

- global time-based holdout split;
- default split sizes: 70% train, 15% validation, 15% test;
- rows sorted by `timestamp`;
- no random shuffle;
- dummy baseline trained alongside baseline and CatBoost models;
- CatBoost receives validation data when available.

Additional research tooling is available outside the main pipeline:

- period stability analysis;
- walk-forward fold generation;
- walk-forward evaluation CLI;
- feature ablation CLI.

These tools support stronger investigation but do not automatically make a run
production-grade or profitable.

## 9. Metrics

The evaluator computes:

- accuracy;
- precision;
- recall;
- f1;
- roc_auc;
- confusion matrix.

The reporting layer can also produce:

- target distribution chart;
- metrics comparison chart;
- CatBoost feature importance chart;
- stability table by period;
- stability plot by period.

If probability scores are unavailable, `roc_auc` is reported as `None`. If a
test segment contains only one class, `roc_auc` is also reported as `None`.

## 10. Evaluation Data

The repository includes a reproducible synthetic sample experiment:

- EDA report: [`eda_sample_dataset.md`](eda_sample_dataset.md);
- experiment summary: [`experiment_summary_sample.md`](experiment_summary_sample.md).

The sample experiment validates pipeline mechanics and artifact generation. It
does not evaluate real market behavior.

Real Binance results must be evaluated separately, preferably across multiple
periods, folds, horizons, and symbols.

## 11. Limitations

Known limitations:

- cryptocurrency markets are noisy and non-stationary;
- short historical windows can produce misleading metrics;
- no fees, slippage, spreads, latency, or execution constraints are modeled;
- no live monitoring or drift detection is implemented;
- no causal claim is made about features and future price movement;
- the main dashboard pipeline currently uses one time-based holdout split;
- walk-forward and ablation tools are available as offline utilities, not as
  first-class dashboard reports;
- local filesystem artifacts and SQLite metadata are intended for local MVP use.

## 12. Risks

Potential risks:

- overfitting to a short or synthetic period;
- accidental data leakage in future feature additions;
- unstable performance across regimes or symbols;
- misinterpreting classification metrics as trading profitability;
- using outputs as financial advice;
- trusting high metrics without dummy baseline, walk-forward validation, or
  stability checks.

## 13. Mitigations

Current mitigations:

- time-based split with no random shuffle;
- explicit exclusion of `target`, `timestamp`, and `symbol` from features;
- dummy baseline for naive comparison;
- LogisticRegression baseline before CatBoost interpretation;
- period stability analysis;
- walk-forward evaluation tooling;
- feature ablation tooling;
- generated reports and saved artifacts for inspectability;
- documentation that separates pipeline validation from market inference.

Recommended future mitigations:

- broader walk-forward reporting;
- validation across symbols, intervals, and market regimes;
- probability calibration;
- transaction cost and execution-aware evaluation before any trading-related
  interpretation;
- monitoring for data drift and model degradation.

## 14. Reproducibility

Reproducibility assets:

- committed synthetic sample dataset: `data/samples/sample_ohlcv.csv`;
- sample EDA report: `docs/eda_sample_dataset.md`;
- sample experiment summary: `docs/experiment_summary_sample.md`;
- CLI commands for CSV and Binance pipelines;
- local artifacts under `media/`;
- SQLite metadata for `PipelineRun`, dataset artifacts, model artifacts,
  metrics, and reports;
- automated checks through Django, Ruff, and unittest.

Example offline command:

```powershell
.crypto\Scripts\python.exe manage.py run_csv_pipeline --csv data/samples/sample_ohlcv.csv --symbol BTCUSDT --interval 1h --start-date 2024-01-01 --end-date 2024-01-10 --target-horizon 3
```

Standard checks:

```powershell
.crypto\Scripts\python.exe manage.py check
.crypto\Scripts\python.exe -m ruff check .
.crypto\Scripts\python.exe -m ruff format --check .
.crypto\Scripts\python.exe -m unittest discover
```

## 15. Version / Status

Status: MVP research pipeline.

Current storage model:

- local filesystem for datasets, models, and report files;
- SQLite for metadata and artifact paths.

The system is suitable for local experimentation and research workflow
inspection. It is not a production trading system.
