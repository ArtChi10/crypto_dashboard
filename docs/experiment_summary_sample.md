# Reproducible Experiment Summary: Synthetic Sample Dataset

## Scope

This summary records one reproducible local pipeline run on the committed sample
dataset:

```text
data/samples/sample_ohlcv.csv
```

The dataset is deterministic and synthetic. It is useful for validating pipeline
mechanics without Binance/network access. It is not real market data and should
not be used for claims about market predictability or trading performance.

Recorded local run:

| Field | Value |
| --- | --- |
| Run id | `960` |
| Status | `success` |
| Dataset | `data/samples/sample_ohlcv.csv` |
| Symbol | `BTCUSDT` |
| Interval | `1h` |
| Target horizon | `3` |
| Last reproduced in this workspace | `2026-05-02` |

Re-running the command will create a new `PipelineRun` id and timestamped
artifact paths. The model and metric values are expected to be reproducible for
the committed sample dataset under the current code and fixed seeds, but this
document should still be treated as a recorded smoke experiment, not a market
benchmark.

## Command

```powershell
.crypto\Scripts\python.exe manage.py run_csv_pipeline --csv data/samples/sample_ohlcv.csv --symbol BTCUSDT --interval 1h --start-date 2024-01-01 --end-date 2024-01-10 --target-horizon 3
```

## Pipeline Parameters

| Parameter | Value |
| --- | --- |
| Input source | CSV |
| Dataset type | Deterministic synthetic OHLCV |
| Start date | `2024-01-01` |
| End date | `2024-01-10` |
| Target definition | `1 if close(t + 3) > close(t), else 0` |
| Split strategy | Global time-based holdout |
| Train / valid / test split | `70% / 15% / 15%` |
| Random shuffle | No |
| Models | DummyClassifier, LogisticRegression baseline, CatBoostClassifier |

## Pipeline Outputs

Dataset artifacts from the recorded run:

| Artifact type | Rows | Example local path |
| --- | ---: | --- |
| raw | 240 | `datasets/raw/raw_run_960_BTCUSDT_20260502_150213.csv` |
| processed | 240 | `datasets/processed/processed_run_960_BTCUSDT_20260502_150213.parquet` |
| final | 223 | `datasets/final/final_run_960_BTCUSDT_20260502_150213.parquet` |

Model artifacts from the recorded run:

| Model | Train rows | Valid rows | Test rows | Feature count | Example local path |
| --- | ---: | ---: | ---: | ---: | --- |
| dummy | 156 | 33 | 34 | 19 | `models/model_dummy_run_960_20260502_150213.joblib` |
| baseline | 156 | 33 | 34 | 19 | `models/model_baseline_run_960_20260502_150213.joblib` |
| catboost | 156 | 33 | 34 | 19 | `models/model_catboost_run_960_20260502_150214.cbm` |

Report artifacts from the recorded run:

| Report type | Example local path |
| --- | --- |
| `target_distribution` | `reports/target_distribution_run_960_20260502_150213.png` |
| `metrics_plot` | `reports/metrics_plot_run_960_20260502_150214.png` |
| `feature_importance` | `reports/feature_importance_run_960_20260502_150214.png` |
| `stability_table` | `reports/stability_table_run_960_20260502_150214.csv` |
| `stability_plot` | `reports/stability_plot_run_960_20260502_150214.png` |

Generated `media/` files from the run are local runtime artifacts and are not
committed to git.

## Metrics

Metrics are computed on the chronological holdout test segment with `34` rows.

| Model | Accuracy | Precision | Recall | F1 | ROC AUC |
| --- | ---: | ---: | ---: | ---: | ---: |
| dummy | 0.5294 | 0.0000 | 0.0000 | 0.0000 | 0.5000 |
| baseline | 0.9706 | 0.9412 | 1.0000 | 0.9697 | 1.0000 |
| catboost | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |

Confusion matrices use sklearn order `[[TN, FP], [FN, TP]]`.

| Model | Confusion matrix |
| --- | --- |
| dummy | `[[18, 0], [16, 0]]` |
| baseline | `[[17, 1], [0, 16]]` |
| catboost | `[[18, 0], [0, 16]]` |

The dummy model predicts the majority class from the training split. It provides
a naive reference point and shows why comparison against trivial behavior is
needed.

## Stability Summary

The pipeline generated both a `stability_table` CSV and a `stability_plot` PNG.
For this recorded run, the stability table contains `6` rows:

```text
3 models x 2 test periods
```

Compact stability rows:

| Model | Period start | Period end | Rows | Positive rate | Accuracy | F1 | ROC AUC |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |
| dummy | `2024-01-09 11:00:00` | `2024-01-09 23:00:00` | 13 | 0.2308 | 0.7692 | 0.0000 | 0.5000 |
| dummy | `2024-01-10 00:00:00` | `2024-01-10 20:00:00` | 21 | 0.6190 | 0.3810 | 0.0000 | 0.5000 |
| baseline | `2024-01-09 11:00:00` | `2024-01-09 23:00:00` | 13 | 0.2308 | 1.0000 | 1.0000 | 1.0000 |
| baseline | `2024-01-10 00:00:00` | `2024-01-10 20:00:00` | 21 | 0.6190 | 0.9524 | 0.9630 | 1.0000 |
| catboost | `2024-01-09 11:00:00` | `2024-01-09 23:00:00` | 13 | 0.2308 | 1.0000 | 1.0000 | 1.0000 |
| catboost | `2024-01-10 00:00:00` | `2024-01-10 20:00:00` | 21 | 0.6190 | 1.0000 | 1.0000 | 1.0000 |

The stability table is intentionally small because the sample dataset covers
only ten synthetic days and the holdout test segment covers the final part of
that period.

## Interpretation

This experiment validates the mechanical reproducibility of the current MVP:

- CSV ingestion works without network access.
- Raw, processed, and final dataset artifacts are created.
- Dummy, LogisticRegression, and CatBoost models are trained and saved.
- Metrics and confusion matrices are persisted.
- Target distribution, metrics comparison, feature importance, and stability
  reports are generated.

The strong baseline and CatBoost metrics are expected on this deterministic
synthetic sample. They should be read as a pipeline sanity check, not evidence
that the approach predicts real crypto markets.

Real market evaluation requires:

- Binance or other real OHLCV periods;
- walk-forward evaluation across multiple folds;
- stability analysis across periods and regimes;
- feature ablation checks;
- comparison against naive baselines;
- explicit modeling of fees, slippage, and execution constraints before any
  trading-related interpretation.
