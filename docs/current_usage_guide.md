# Current usage guide

Это руководство описывает текущее состояние проекта `crypto_dashboard`.
Оно не описывает будущую версию и не обещает функциональность, которой пока
нет в коде.

## Что это за проект

`crypto_dashboard` - это Django-приложение для учета запусков ML-пайплайна,
который должен прогнозировать направление цены криптовалют.

Сейчас проект умеет хранить metadata о запусках, показывать обзорный Dashboard
и Runs, запускать pipeline из Binance через `/binance/`, запускать pipeline из
CSV через `/upload/`, хранить ссылки на dataset/model/report artifacts и
запускать research/ML-компоненты из Python или CLI.

Research report skeleton: [`docs/research_report.md`](research_report.md).
Model card: [`docs/model_card.md`](model_card.md).
Real data dataset manifest guide:
[`docs/real_data_dataset_manifest.md`](real_data_dataset_manifest.md).

Главное правило хранения:

```text
Django DB = metadata only
local default = SQLite
Docker/production = PostgreSQL through DATABASE_URL
media/ = большие файлы datasets, models, reports
```

Локальные manual/test artifacts, например `manual_upload_test.csv` и временные
папки `tmp_*`, не коммитятся. Они используются только для smoke checks и
локальной ручной проверки.

GitHub Actions CI запускает тот же базовый набор проверок на `push` и
`pull_request`: `manage.py check`, `ruff check`, `ruff format --check` и
`manage.py test`.

## Environment variables

Django settings читают optional environment variables:

- `DJANGO_SECRET_KEY` - local/project secret key value;
- `DJANGO_DEBUG` - `True` or `False`;
- `DJANGO_ALLOWED_HOSTS` - comma-separated host list.

Defaults в `config/settings.py` подходят для local development и тестов:
`DJANGO_SECRET_KEY` получает placeholder `dev-insecure-local-key`,
`DJANGO_DEBUG=True`, а `ALLOWED_HOSTS` включает `localhost`, `127.0.0.1` и
`testserver`. Пример значений хранится в `.env.example`; реальный `.env`
игнорируется git и не должен коммититься.

## Docker local stack

Для локального контейнерного запуска есть Docker Compose stack:

```powershell
docker compose build
docker compose up
```

После старта открыть:

```text
http://localhost:8000/
```

Остановить stack:

```powershell
docker compose down
```

Docker stack использует PostgreSQL через `DATABASE_URL`, выполняет migrations,
собирает static files через `collectstatic` и запускает Django через Gunicorn.
Локальный `.crypto` workflow по-прежнему использует SQLite, если
`DATABASE_URL` не задан в shell environment.

## Production-oriented Docker Compose

Для серверного HTTP setup без HTTPS добавлен отдельный compose file:
`docker-compose.prod.yml`. Он описывает services `web`, `db` и `proxy`:

- `web` - Django + Gunicorn;
- `db` - PostgreSQL 16;
- `proxy` - Caddy на HTTP `:80`, static/media и reverse proxy to `web:8000`.

Пример env лежит в `.env.production.example`. Реальный `.env.production`
игнорируется git и должен содержать server IP/secret/password values.

Подробная инструкция: [`docs/deployment_guide.md`](deployment_guide.md).

## Что уже работает

- Django project `config`.
- Django apps `dashboard` и `runs`.
- Django metadata models:
  - `PipelineRun`;
  - `DatasetArtifact`;
  - `ModelArtifact`;
  - `MetricSnapshot`;
  - `ReportArtifact`.
- Django admin для этих models.
- `MEDIA_ROOT` и `MEDIA_URL` для файлового storage.
- Главная страница `/`.
- История запусков `/runs/`.
- Детальная страница запуска `/runs/<id>/`.
- Минимальный общий UI layout и CSS для Dashboard, Upload, Binance и Runs pages.
- Обзорный Dashboard со ссылками на реальные pipeline entry points.
- Страница `/upload/` для ручной загрузки raw OHLCV CSV, сохранения raw artifact
  и синхронного запуска pipeline.
- Страница `/binance/` для загрузки OHLCV candles из Binance, синхронного
  запуска pipeline и optional Forecast Replay по будущему окну после `end_date`.
- `ArtifactRepository` для построения путей artifacts.
  Он централизованно знает все dataset/model/report types, включая
  `stability_table`, `stability_plot`, `forecast_replay` и
  `forecast_replay_table`.
- `DatasetRepository` для сохранения и загрузки `.csv` и `.parquet`.
- `BinanceMarketDataProvider` для загрузки OHLCV candles из Binance Spot REST API
  в pandas `DataFrame`.
- `DataCleaner` для очистки OHLCV-данных.
- `FeatureBuilder` для построения признаков.
- `TargetBuilder` для построения target-колонки.
- `DatasetPreparationService` для ручной подготовки processed/final datasets из Python.
- `SplitService` для временного train/valid/test split.
- `WalkForwardValidationService` для research-разбиения временного ряда на
  последовательные train/test folds без random shuffle.
- `WalkForwardEvaluationService` для fold-by-fold обучения и оценки trainer без
  интеграции в основной pipeline.
- `FeatureAblationService` для research-сравнения групп признаков через
  `all_features` и `without_<group>` experiments.
- `ForecastReplayService` для reusable classification replay/reality check
  таблицы по history/future candles и уже обученной модели.
- `Evaluator` для расчета classification metrics.
- `PeriodStabilityAnalysisService` для research-анализа metrics по временным
  сегментам predictions.
- `BaselineTrainer` на базе `LogisticRegression`.
- `DummyBaselineTrainer` на базе `DummyClassifier` как naive baseline.
- `CatBoostTrainer`.
- `ModelRepository` для сохранения и загрузки `.joblib`, `.pkl`, `.cbm`.
- `DummyTrainingService` для обучения и оценки naive baseline.
- `BaselineTrainingService` для ручного обучения baseline-модели из Python.
- `CatBoostTrainingService` для ручного обучения CatBoost-модели из Python.
- `TargetDistributionReportService` для PNG-отчета распределения target.
- `MetricsComparisonReportService` для PNG-сравнения metrics по моделям.
- `PeriodStabilityReportService` для CSV/PNG отчета стабильности metrics по
  временным периодам test predictions.
- `ForecastReplayReportService` для PNG-графика history/replay close и
  predicted up/down markers.
- `FeatureImportanceReportService` для PNG-отчета важности CatBoost-признаков.
- `FullPipelineService` для ручного in-memory запуска preparation + training из Python.
- `RunPersistenceService` для сохранения результатов pipeline в Django metadata.
- `RunPipelineUseCase` для orchestration одного `PipelineRun` из Python.
- `CsvPipelineUploadUseCase` для orchestration ручной CSV-загрузки из UI и CLI.
- Management command `run_csv_pipeline` для запуска pipeline из CSV через CLI.
- Management command `run_binance_pipeline` для загрузки Binance OHLCV и запуска
  pipeline через CLI.
- Management command `run_research_evaluation` для offline research checks по
  final parquet/csv dataset без записи в Django metadata.

## Что еще не работает

- Нет async/background queue: CSV upload и Binance page запускают pipeline
  синхронно.
- Dashboard не запускает pipeline напрямую; он только показывает overview,
  последние runs и ссылки на `/binance/`, `/upload/`, `/runs/`.
- Forecast Replay подключен к `/binance/` как optional reality-check flow, но это
  synchronous replay/backtest visualization, а не live forecasting.

## Окружение

Используйте виртуальное окружение `.crypto`.

Рекомендуемый способ запускать команды из корня проекта:

```powershell
.crypto\Scripts\python.exe manage.py check
```

Можно активировать окружение в PowerShell:

```powershell
.\.crypto\Scripts\Activate.ps1
```

После активации можно запускать `python manage.py ...`, но в этом проекте
предпочтительно использовать явный путь:

```powershell
.crypto\Scripts\python.exe ...
```

Если PowerShell запрещает запуск `Activate.ps1`, не меняйте настройки ради
этого: используйте прямой вызов `.crypto\Scripts\python.exe`.

## Как запустить проверки

Команды нужно запускать из корня проекта:

```powershell
.crypto\Scripts\python.exe manage.py check
.crypto\Scripts\python.exe -m ruff check .
.crypto\Scripts\python.exe -m ruff format --check .
.crypto\Scripts\python.exe manage.py test
```

Что делают команды:

- `manage.py check` проверяет Django-настройки и конфигурацию проекта.
- `ruff check .` запускает lint-проверку Python-кода.
- `ruff format --check .` проверяет форматирование без изменения файлов.
- `manage.py test` запускает Django test runner с test database и migrations.

## Как запустить сервер

Из корня проекта:

```powershell
.crypto\Scripts\python.exe manage.py runserver
```

По умолчанию Django запустит dev-сервер на:

```text
http://127.0.0.1:8000/
```

Если порт занят, можно указать другой:

```powershell
.crypto\Scripts\python.exe manage.py runserver 127.0.0.1:8001
```

## Как открыть Dashboard

1. Запустите сервер:

```powershell
.crypto\Scripts\python.exe manage.py runserver
```

2. Откройте в браузере:

```text
http://127.0.0.1:8000/
```

На главной странице сейчас видны:

- название проекта;
- количество запусков;
- короткое объяснение проекта;
- ссылки на реальные entry points `/binance/`, `/upload/`, `/runs/`;
- ссылка на историю `/runs/`;
- ссылка на ручную загрузку `/upload/`;
- таблица последних запусков.

Dashboard больше не создает пустые `PipelineRun` records. POST-запросы на `/`
не принимаются.

## Как запустить pipeline через UI

1. Для Binance откройте:

```text
http://127.0.0.1:8000/binance/
```

Выберите symbol, interval, date range, target horizon и модели. Optional
`Enable forecast replay` докачивает будущие candles после `end_date`, строит
CSV/PNG replay reports и показывает их на `/runs/<id>/` вместе с summary и
preview table.
Страница также содержит короткую contextual help-подсказку: что такое Binance
Spot OHLCV candles, примеры `BTCUSDT`/`1h`, смысл `target_horizon` и какие
artifacts появятся после запуска. Replay показывает predicted up/down против
факта, но не является прогнозом цены или trading signal.

2. Для CSV откройте:

```text
http://127.0.0.1:8000/upload/
```

Загрузите CSV с колонками `timestamp`, `open`, `high`, `low`, `close`,
`volume`, `symbol`. UI-подсказка на странице отдельно выделяет required columns,
recommended `symbol`, sample path `data/samples/sample_ohlcv.csv` и объясняет,
что upload сохраняет raw artifact, а затем запускает общий ML pipeline.

3. После запуска pipeline результат открывается на `/runs/<id>/`; всю историю
можно смотреть на `/runs/`.

## Как загрузить raw CSV и запустить pipeline

1. Откройте страницу:

```text
http://127.0.0.1:8000/upload/
```

2. Загрузите CSV с колонками:

```text
timestamp, open, high, low, close, volume, symbol
```

3. Заполните metadata:

- `symbol`;
- `interval`;
- `start_date`;
- `end_date`;
- `target_horizon`;
- `train_baseline`;
- `train_catboost`.

4. Нажмите `Загрузить CSV и запустить pipeline`.

После отправки формы view вызывает `CsvPipelineUploadUseCase`. Этот use case
создает `PipelineRun`, читает CSV через pandas, сохраняет исходный CSV в
`media/datasets/raw/` через `DatasetRepository`, создает `DatasetArtifact` с
`artifact_type="raw"`, `symbol` и `row_count`, а затем запускает
`RunPipelineUseCase`.

Для MVP запуск выполняется синхронно прямо во время POST-запроса. После успеха
страница перенаправляет на `/runs/<id>/`, где видны raw/processed/final
`DatasetArtifact`, `ModelArtifact` и `MetricSnapshot`.

Если CSV некорректный или pipeline падает, страница тоже перенаправляет на
`/runs/<id>/`, а `PipelineRun.status` становится `Failed` и ошибка записывается
в `PipelineRun.error_message`. Если ошибка произошла после сохранения raw CSV,
raw artifact остается у запуска для воспроизводимости.

## Как запустить pipeline на Binance data из веб-формы

1. Откройте страницу:

```text
http://127.0.0.1:8000/binance/
```

2. Заполните параметры:

- `symbol`, по умолчанию `BTCUSDT`;
- `interval`, по умолчанию `1h`;
- `start_date`;
- `end_date`;
- `target_horizon`, по умолчанию `3`;
- `train_baseline`;
- `train_catboost`;
- `enable_forecast_replay`;
- `replay_steps`, по умолчанию `5`.

3. Нажмите `Скачать Binance data и запустить pipeline`.

После отправки формы view вызывает `BinancePipelineUseCase`. Этот use case
скачивает OHLCV через `BinanceMarketDataProvider`, сохраняет raw Binance dataset
как parquet `DatasetArtifact(type="raw")`, запускает `RunPipelineUseCase` и
перенаправляет на `/runs/<id>/`.

Если `enable_forecast_replay` включен, `BinancePipelineUseCase` дополнительно
скачивает future window после `end_date`. `FullPipelineService` выбирает модель
в порядке `catboost -> baseline -> dummy`, строит replay table через
`ForecastReplayService`, сохраняет `forecast_replay_table` CSV и
`forecast_replay` PNG. `RunPersistenceService` сохраняет оба файла как
`ReportArtifact`, поэтому `/runs/<id>/` показывает отдельный Forecast Replay
summary block, CSV preview, PNG в существующей report gallery и link на полный
CSV.

Если обе модели выключены, форма покажет ошибку и pipeline не запустится. Если
ошибка произошла после создания run, страница перенаправит на detail page, где
будет виден статус `Failed` и текст ошибки.

## Manual Test Phase 3: Binance Pipeline UI

Manual Test Phase 3 пройден успешно: Binance Pipeline UI запускает реальный
MVP-пайплайн из веб-интерфейса.

Проверено вручную:

- `/binance/` открывается и показывает Binance form;
- форма Binance запускает real network pipeline через Binance Spot REST API;
- создаются raw, processed и final datasets;
- создаются dummy, baseline и CatBoost model artifacts;
- создаются `MetricSnapshot` для моделей;
- создаются PNG reports: target distribution, metrics comparison и CatBoost
  feature importance;
- создаются period stability reports: CSV table и PNG plot;
- detail page `/runs/<id>/` показывает artifacts, metrics и inline PNG reports.

Важно: высокие metrics на коротком периоде не доказывают рыночную
предсказательность. Это research/MVP pipeline для воспроизводимых экспериментов,
а не production trading system.

## Как запустить raw CSV pipeline из CLI

Management command использует тот же `CsvPipelineUploadUseCase`, что и страница
`/upload/`. Команда не дублирует pipeline-логику, а только проверяет CLI-аргументы
и передает CSV-файл в use case.

Для offline demo в репозитории есть deterministic synthetic sample dataset:
`data/samples/sample_ohlcv.csv`. Он не требует Binance/network access и нужен
для smoke checks. Это не реальные рыночные данные и не доказательство качества
модели.

Краткий EDA report по sample dataset доступен здесь:
[`docs/eda_sample_dataset.md`](eda_sample_dataset.md).
Записанный reproducible experiment summary по sample run доступен здесь:
[`docs/experiment_summary_sample.md`](experiment_summary_sample.md).

Пример:

```powershell
.crypto\Scripts\python.exe manage.py run_csv_pipeline --csv data/samples/sample_ohlcv.csv --symbol BTCUSDT --interval 1h --start-date 2024-01-01 --end-date 2024-01-10 --target-horizon 3
```

Опциональные flags:

- `--skip-baseline` - не обучать baseline-модель;
- `--skip-catboost` - не обучать CatBoost-модель.

Нельзя указать оба skip flags одновременно: pipeline должен обучить хотя бы одну
модель. При успехе команда выводит `run id`, `run status` и detail URL вида
`/runs/<id>/`. При ошибке команда завершится через `CommandError`; если
`PipelineRun` уже был создан, его статус станет `failed`, а ошибка попадет в
`PipelineRun.error_message`.

## Как запустить pipeline на Binance data из CLI

Management command `run_binance_pipeline` скачивает OHLCV candles через
`BinanceMarketDataProvider`, создает `PipelineRun`, сохраняет raw Binance dataset
как parquet `DatasetArtifact(type="raw")`, а затем запускает существующий
`RunPipelineUseCase`.

Пример:

```powershell
.crypto\Scripts\python.exe manage.py run_binance_pipeline --symbol BTCUSDT --interval 1h --start-date 2024-01-01 --end-date 2024-01-10 --target-horizon 3 --skip-catboost
```

Аргументы:

- `--symbol` - один trading symbol, например `BTCUSDT`;
- `--interval` - candle interval, по умолчанию `1h`;
- `--start-date` и `--end-date` - даты в формате `YYYY-MM-DD`;
- `--target-horizon` - horizon для target, по умолчанию `3`;
- `--skip-baseline` - не обучать baseline;
- `--skip-catboost` - не обучать CatBoost.

Если одновременно передать `--skip-baseline` и `--skip-catboost`, команда
завершится `CommandError` до создания run. При успехе выводятся `run id`,
`run status` и detail URL вида `/runs/<id>/`. При ошибке после создания run его
статус станет `failed`, а ошибка попадет в `PipelineRun.error_message`.

## Как заморозить real Binance dataset для research benchmark

Для больших research runs лучше использовать frozen dataset, а не каждый раз
делать live-запрос к Binance. Script:

```text
scripts/freeze_binance_dataset.py
```

скачивает OHLCV через `BinanceMarketDataProvider`, сохраняет parquet в ignored
folder `data/real/` и рядом пишет manifest JSON с параметрами запроса, row count,
timestamp range, missing values, duplicate timestamp count и SHA256 файла.

Recommended first benchmark:

```powershell
.crypto\Scripts\python.exe scripts\freeze_binance_dataset.py --symbol BTCUSDT --interval 1h --start-date 2025-01-01 --end-date 2025-07-01 --output-dir data\real
```

Smoke command на коротком периоде:

```powershell
.crypto\Scripts\python.exe scripts\freeze_binance_dataset.py --symbol BTCUSDT --interval 1h --start-date 2025-01-01 --end-date 2025-01-10 --output-dir data\real
```

`data/real/` добавлен в `.gitignore`, поэтому generated parquet и manifest не
попадают в commit. Публичное описание schema manifest лежит в
[`docs/real_data_dataset_manifest.md`](real_data_dataset_manifest.md).

После freeze можно сгенерировать real-data EDA report:

```powershell
.crypto\Scripts\python.exe scripts\generate_real_data_eda.py --dataset data\real\binance_BTCUSDT_1h_2025-01-01_2025-01-10.parquet --manifest data\real\binance_BTCUSDT_1h_2025-01-01_2025-01-10.manifest.json --output-doc docs\real_data_eda.md --output-dir docs\assets\real_data_eda --horizons 1,3,6,12
```

Report `docs/real_data_eda.md` показывает manifest, schema/data quality,
price/volume overview, returns distribution, rolling volatility и target balance
по horizons `1,3,6,12`.

После EDA можно запустить первый real-data walk-forward benchmark на frozen
dataset. Script применяет тот же `DataCleaner -> FeatureBuilder ->
TargetBuilder`, запускает trainers `dummy`, `baseline`, `catboost`, сохраняет
fold CSV, plots и markdown report:

```powershell
.crypto\Scripts\python.exe scripts\run_real_data_walk_forward_benchmark.py --dataset data\real\binance_BTCUSDT_1h_2025-01-01_2025-01-10.parquet --manifest data\real\binance_BTCUSDT_1h_2025-01-01_2025-01-10.manifest.json --output-doc docs\real_data_walk_forward_benchmark.md --output-dir docs\assets\real_data_walk_forward --target-horizon 3 --train-window 120 --test-window 24 --step 24 --trainers dummy,baseline,catboost --bootstrap-samples 1000 --confidence-level 0.95 --random-state 42
```

Report `docs/real_data_walk_forward_benchmark.md` показывает manifest/hash,
walk-forward setup, summary metrics, bootstrap confidence intervals и
fold-level outputs. `--bootstrap-samples`, `--confidence-level` и
`--random-state` управляют CI. На коротком smoke dataset с малым числом folds
intervals являются только uncertainty signal, не statistical proof. Это
stability check directional classification metrics, не trading/performance
claim.

Для regime diagnostics по volatility/trend buckets используйте:

```powershell
.crypto\Scripts\python.exe scripts\run_real_data_regime_analysis.py --dataset data\real\binance_BTCUSDT_1h_2025-01-01_2025-01-10.parquet --manifest data\real\binance_BTCUSDT_1h_2025-01-01_2025-01-10.manifest.json --output-doc docs\real_data_regime_analysis.md --output-dir docs\assets\real_data_regime_analysis --trainer baseline --target-horizon 3 --train-window 120 --test-window 24 --step 24 --trend-window 24 --trend-threshold 0.01
```

Report `docs/real_data_regime_analysis.md` показывает row-level predictions,
metrics by volatility regime, metrics by trend regime и error counts. Threshold
`--trend-threshold` является heuristic diagnostic setting, не trading rule.

Для детального error analysis по walk-forward predictions используйте:

```powershell
.crypto\Scripts\python.exe scripts\run_real_data_error_analysis.py --dataset data\real\binance_BTCUSDT_1h_2025-01-01_2025-01-10.parquet --manifest data\real\binance_BTCUSDT_1h_2025-01-01_2025-01-10.manifest.json --output-doc docs\real_data_error_analysis.md --output-dir docs\assets\real_data_error_analysis --trainer baseline --target-horizon 3 --train-window 120 --test-window 24 --step 24 --trend-window 24 --trend-threshold 0.01 --top-n 10
```

Report `docs/real_data_error_analysis.md` показывает false positives, false
negatives, high-confidence mistakes, confidence-bin error rates и error rates by
volatility/trend regime. High-confidence mistakes полезны как model-risk
examples, но не являются торговыми сигналами.

Важно: это real market data для research benchmark. Оно не доказывает trading
performance и не является основанием для live trading decisions.

## Как запустить research evaluation из CLI

Management command `run_research_evaluation` запускает offline research checks
по уже подготовленному final dataset. Он не создает `PipelineRun`, не пишет в
Django DB, не создает `ReportArtifact` и не запускает main pipeline. Результаты
сохраняются обычными CSV-файлами в `--output-dir`.

```powershell
.crypto\Scripts\python.exe manage.py run_research_evaluation --dataset tmp_research_check/final.parquet --output-dir tmp_research_check/out --trainer dummy --run-walk-forward --run-ablation --train-window 40 --test-window 20
```

Аргументы:

- `--dataset` - путь к final `.parquet` или `.csv` dataset;
- `--output-dir` - директория для CSV outputs, по умолчанию `research_outputs`;
- `--target-col` - имя target column, по умолчанию `target`;
- `--trainer` - `dummy`, `baseline` или `catboost`;
- `--run-walk-forward` - сохранить `walk_forward_<trainer>.csv`;
- `--run-ablation` - сохранить `ablation_<trainer>.csv`;
- `--train-window`, `--test-window`, `--step` - параметры walk-forward windows.

Для ablation command делает простой 70/30 split по `timestamp`. CatBoost в
research CLI использует быстрые параметры, но все равно может быть медленнее
`dummy` и `baseline`; для быстрых checks используйте более простые trainers.

## Как открыть /runs/ и /runs/<id>/

История запусков:

```text
http://127.0.0.1:8000/runs/
```

На странице `/runs/` отображается таблица `PipelineRun` с пагинацией по 25
записей на страницу. Над таблицей есть короткая подсказка по статусам:
`created`, `running`, `success`, `failed`. После упрощения Dashboard новые
`created` records не должны появляться через `/`, но старые metadata records
могут оставаться в истории.

Детальная страница запуска:

```text
http://127.0.0.1:8000/runs/1/
```

Замените `1` на нужный `id`.

На странице `/runs/<id>/` отображаются:

- параметры `PipelineRun`;
- `DatasetArtifact`;
- `ModelArtifact`;
- `MetricSnapshot`;
- `ReportArtifact`;
- сообщение об ошибке, если оно записано в `PipelineRun.error_message`.

Перед основными секциями detail page есть короткие contextual notes:
`DatasetArtifact` объясняет raw/processed/final datasets, `ModelArtifact` -
сохраненные models и row counts, `MetricSnapshot` - test metrics и confusion
matrix, `ReportArtifact` - PNG/CSV reports, а `Stability by Period` - метрики
по временным периодам.

Для artifacts, которые лежат внутри `MEDIA_ROOT`, `file_path` показывается как
ссылка вида `/media/...`. Для model artifacts страница выводит summary из
`params_json`: `train_rows`, `valid_rows`, `test_rows` и `feature_count`.
Classification metrics округляются до 4 знаков, а confusion matrix показывается
в читаемом виде. PNG-файлы `ReportArtifact` из `media/reports/` дополнительно
показываются прямо на странице как inline images; ссылка на файл при этом
остается кликабельной. Non-PNG reports и небезопасные пути отображаются без
inline image. Если у run есть безопасный `stability_table` CSV внутри
`media/reports/`, detail page показывает компактный preview первых 20 строк:
`model_type`, период, rows, `accuracy`, `f1` и `roc_auc`. Полная CSV-ссылка
остается доступной.

Если artifacts или metrics еще не созданы, соответствующие таблицы будут
пустыми.

## Как пользоваться admin

Admin доступен по адресу:

```text
http://127.0.0.1:8000/admin/
```

Если superuser еще не создан, создайте его:

```powershell
.crypto\Scripts\python.exe manage.py createsuperuser
```

После входа в admin можно смотреть и редактировать metadata:

- `PipelineRun`;
- `DatasetArtifact`;
- `ModelArtifact`;
- `MetricSnapshot`;
- `ReportArtifact`.

Admin полезен для ручной проверки записей в SQLite. Он не является pipeline
runner и сам не обучает модели.

## Как запустить tests

```powershell
.crypto\Scripts\python.exe manage.py test
```

Тесты лежат в папке `tests/` и проверяют repositories, preprocessing, features,
targets, split, trainers, evaluator, `DatasetPreparationService`,
`BaselineTrainingService`, `CatBoostTrainingService`, `FullPipelineService`,
`RunPersistenceService` и `RunPipelineUseCase`.

## Как запустить Ruff

Lint:

```powershell
.crypto\Scripts\python.exe -m ruff check .
```

Проверка форматирования:

```powershell
.crypto\Scripts\python.exe -m ruff format --check .
```

Если нужно автоматически отформатировать Python-код:

```powershell
.crypto\Scripts\python.exe -m ruff format .
```

## Как вручную проверить DatasetPreparationService

`DatasetPreparationService` можно запустить из Python на маленьком synthetic
OHLCV dataset. Пример ниже не использует UI и не создает `DatasetArtifact` в
SQLite. Он чистит raw данные, строит features и target, сохраняет processed и
final datasets в parquet.

```powershell
.crypto\Scripts\python.exe -c "from pathlib import Path; import pandas as pd; from mlcore.repositories import ArtifactRepository; from mlcore.services import DatasetPreparationService; df = pd.DataFrame({'timestamp': pd.date_range('2024-01-01', periods=60, freq='h'), 'open': range(1, 61), 'high': range(2, 62), 'low': range(0, 60), 'close': range(1, 61), 'volume': range(100, 160), 'symbol': ['BTCUSDT'] * 60}); service = DatasetPreparationService(artifact_repository=ArtifactRepository(Path('tmp_artifacts/manual_dataset_preparation_check'))); result = service.prepare(df, run_id=1, horizon=3, symbol='BTCUSDT'); print('processed_path=', result.processed_path); print('final_path=', result.final_path); print('rows=', result.raw_rows, result.processed_rows, result.final_rows); print('features=', result.feature_columns); print('target=', result.target_column)"
```

Ожидаемый смысл результата:

- `processed_path` показывает путь к очищенному `.parquet` dataset;
- `final_path` показывает путь к `.parquet` dataset с features и target;
- `rows` показывает размеры raw, processed и final datasets;
- `features` содержит feature columns, построенные `FeatureBuilder`;
- `target` равен `target`.

## Как вручную проверить BaselineTrainingService

`BaselineTrainingService` можно запустить из Python на маленьком synthetic
dataset. Пример ниже не использует UI и не записывает metrics в SQLite.
Он обучает baseline-модель, считает metrics на test split и сохраняет `.joblib`
model artifact в `tmp_artifacts/manual_baseline_check/models/`.

```powershell
.crypto\Scripts\python.exe -c "from pathlib import Path; import pandas as pd; from mlcore.repositories import ArtifactRepository; from mlcore.services import BaselineTrainingService; df = pd.DataFrame({'timestamp': pd.date_range('2024-01-01', periods=80, freq='h'), 'symbol': ['BTCUSDT'] * 80, 'feature_1': range(80), 'feature_2': [i % 5 for i in range(80)], 'target': [i % 2 for i in range(80)]}); service = BaselineTrainingService(artifact_repository=ArtifactRepository(Path('tmp_artifacts/manual_baseline_check'))); result = service.train_and_evaluate(df, run_id=1); print('model_path=', result.model_path); print('metrics=', result.metrics); print('features=', result.feature_columns); print('rows=', result.train_rows, result.valid_rows, result.test_rows)"
```

Ожидаемый смысл результата:

- `model_path` показывает путь к сохраненному `.joblib` файлу;
- `metrics` содержит `accuracy`, `precision`, `recall`, `f1`, `roc_auc`,
  `confusion_matrix`;
- `features` показывает numeric feature columns, которые использовала модель;
- `rows` показывает размеры train, valid и test частей.

## Как вручную проверить PeriodStabilityAnalysisService

`PeriodStabilityAnalysisService` - это research utility для уже готовых
predictions. Он не обучает модели. На вход нужен `DataFrame` с колонками
`timestamp`, `y_true`, `y_pred` и, опционально, `y_proba`.

```powershell
.crypto\Scripts\python.exe -c "import pandas as pd; from mlcore.evaluation.stability import PeriodStabilityAnalysisService; df=pd.DataFrame({'timestamp':pd.date_range('2024-01-01', periods=48, freq='h'), 'y_true':[0,1]*24, 'y_pred':[0,1,1,1]*12, 'y_proba':[0.1,0.8,0.6,0.7]*12}); result=PeriodStabilityAnalysisService().analyze_predictions(df, period='D'); print(result[['rows','accuracy','f1','roc_auc']].to_dict('records'))"
```

`period="D"` группирует predictions по дням, `period="W"` - по неделям. Можно
передать любой pandas frequency string. Если в отдельном периоде только один
класс `y_true` или нет `y_proba`, `roc_auc` будет `None`.

В полном pipeline этот анализ уже используется через `PeriodStabilityReportService`.
Он сохраняет:

- `stability_table` как CSV в `media/reports/`;
- `stability_plot` как PNG в `media/reports/`.

## Как вручную понимать ForecastReplayService

`ForecastReplayService` - это reusable core service для режима Forecast Replay /
Reality Check. Он принимает:

- `history_df` с уже известными candles;
- `future_df` с последующими candles для проверки факта;
- обученную classification-модель;
- `feature_columns`;
- `horizon` и `replay_steps`.

Service объединяет history и future только для построения rolling/past features,
затем берет replay-точки из будущего окна и вызывает `model.predict()` только на
переданных `feature_columns`. `future_close` не используется как feature: он
нужен только для проверки факта `actual_direction = 1 if future_close > close`.

Replay output columns:

```text
timestamp, close, future_close, actual_direction, predicted_direction,
predicted_probability, is_correct, actual_change, actual_change_pct,
predicted_label, actual_label, result_label
```

Если model поддерживает `predict_proba`, service сохраняет probability класса 1
в `predicted_probability`; иначе там будет `None`.
`actual_change` и `actual_change_pct` показывают, насколько реально изменилась
цена между replay close и `future_close`; labels `up`/`down`/`correct`/`wrong`
делают CSV и UI preview читаемыми без ручной расшифровки 0/1.

`ForecastReplayReportService` строит PNG-график: historical close, replay close
и крупные markers predicted up/down с correct/incorrect цветом. Title содержит
`correct/total` и hit rate, а probability labels показываются как `P(up)=...`,
если model их дала. В Binance UI эти outputs сохраняются как `forecast_replay`
для PNG и `forecast_replay_table` для CSV. Run detail дополнительно показывает
hit rate, average probability и первые replay rows из safe CSV preview.

Важно: это replay/backtest visualization для classification model, а не live
price forecasting и не trading signal.

## Как вручную проверить WalkForwardValidationService

`WalkForwardValidationService` - это независимый research utility для
walk-forward folds. Он сортирует строки по `timestamp` и строит train/test окна
по количеству строк. По умолчанию `step` равен `test_window`.

```powershell
.crypto\Scripts\python.exe -c "import pandas as pd; from mlcore.evaluation.walk_forward import WalkForwardValidationService; df=pd.DataFrame({'timestamp':pd.date_range('2024-01-01', periods=30, freq='h'), 'x':range(30), 'target':[0,1]*15}); folds=WalkForwardValidationService().split(df, train_window=10, test_window=5); print(len(folds)); print([(f.fold_id, len(f.train), len(f.test), f.train['timestamp'].max() < f.test['timestamp'].min()) for f in folds])"
```

Ожидаемый смысл результата: получится несколько последовательных folds, в
каждом `train` идет раньше `test`.

## Как вручную проверить WalkForwardEvaluationService

`WalkForwardEvaluationService` строит folds через `WalkForwardValidationService`,
на каждом fold обучает переданный trainer, считает metrics через `Evaluator` и
возвращает pandas `DataFrame`. Если обучение отдельного fold падает, например
из-за one-class `y_train`, по умолчанию service записывает `error_message` и
metrics `None`. При `raise_on_error=True` ошибка пробрасывается.

```powershell
.crypto\Scripts\python.exe -c "import pandas as pd; from mlcore.evaluation.walk_forward import WalkForwardEvaluationService; from mlcore.training.dummy_trainer import DummyBaselineTrainer; df=pd.DataFrame({'timestamp':pd.date_range('2024-01-01', periods=60, freq='h'), 'feature_1':range(60), 'feature_2':[x%5 for x in range(60)], 'target':[0,1]*30}); result=WalkForwardEvaluationService().evaluate(DummyBaselineTrainer(), df, train_window=20, test_window=10); print(len(result)); print(list(result.columns)); print(result[['fold_id','train_rows','test_rows','accuracy','f1']].head().to_dict('records'))"
```

Этот service пока не интегрирован в `FullPipelineService`, Django metadata, UI
или report artifacts. Это ручной research-инструмент для проверки идей перед
следующей интеграцией.

## Как вручную проверить FeatureAblationService

`FeatureAblationService` сравнивает вклад feature groups. По умолчанию он знает
группы `price_raw`, `returns`, `moving_average`, `volatility`, `volume` и
`candle`. В режиме `drop_groups` service считает `all_features`, а затем
эксперименты `without_<group>`. Для каждого experiment создается новый trainer
через `trainer_factory`.

```powershell
.crypto\Scripts\python.exe -c "import pandas as pd; from mlcore.evaluation.ablation import FeatureAblationService; from mlcore.training.dummy_trainer import DummyBaselineTrainer; df=pd.DataFrame({'timestamp':pd.date_range('2024-01-01', periods=60, freq='h'), 'open':range(60), 'high':range(1,61), 'low':range(0,60), 'close':range(60), 'return_1':[0.1]*60, 'volume':range(100,160), 'target':[0,1]*30}); train=df.iloc[:40].reset_index(drop=True); test=df.iloc[40:].reset_index(drop=True); result=FeatureAblationService().evaluate_groups(lambda: DummyBaselineTrainer(), train, test); print(result[['experiment','included_feature_count','accuracy','error_message']].head().to_dict('records')); print(len(result))"
```

Если группа признаков отсутствует в `train`/`test`, service не падает: он
возвращает row с `error_message`. Сервис не сохраняет artifacts и пока не
интегрирован в основной pipeline/UI.

## Как вручную проверить FullPipelineService

`FullPipelineService` запускает весь текущий ML-сценарий на переданном raw
`DataFrame`: подготовку датасета, загрузку final parquet и обучение выбранных
моделей. Он не пишет metadata в SQLite и не создает Django artifacts.

Для synthetic данных важно, чтобы после `TargetBuilder` получались оба класса
`target`, иначе LogisticRegression и CatBoost честно откажутся обучаться на
одном классе. Dummy baseline one-class train split разрешает, потому что это
наивная контрольная точка.

```powershell
.crypto\Scripts\python.exe -c "from pathlib import Path; import pandas as pd; from mlcore.repositories import ArtifactRepository; from mlcore.services import CatBoostTrainingService, FullPipelineService; from mlcore.training import CatBoostTrainer; close = [1, 3, 2, 4] * 25; df = pd.DataFrame({'timestamp': pd.date_range('2024-01-01', periods=100, freq='h'), 'open': close, 'high': [x + 1 for x in close], 'low': [x - 1 for x in close], 'close': close, 'volume': range(100, 200), 'symbol': ['BTCUSDT'] * 100}); artifact_repo = ArtifactRepository(Path('tmp_artifacts/manual_full_pipeline_check')); service = FullPipelineService(catboost_training_service=CatBoostTrainingService(artifact_repository=artifact_repo, trainer=CatBoostTrainer(iterations=5, verbose=False))); result = service.run(df, run_id=1, horizon=3, symbol='BTCUSDT'); print('final_path=', result.preparation_result.final_path); print('dummy=', result.dummy_result is not None); print('baseline=', result.baseline_result is not None); print('catboost=', result.catboost_result is not None); print('dummy_metrics=', result.dummy_result.metrics); print('baseline_metrics=', result.baseline_result.metrics); print('catboost_metrics=', result.catboost_result.metrics)"
```

Ожидаемый смысл результата:

- `final_path` показывает путь к сохраненному final parquet dataset;
- `dummy=True` означает, что наивный baseline обучился и сохранился;
- `baseline=True` означает, что baseline-модель обучилась и сохранилась;
- `catboost=True` означает, что CatBoost-модель обучилась и сохранилась;
- `dummy_metrics`, `baseline_metrics` и `catboost_metrics` содержат classification
  metrics.

## Как сохранять metadata результата pipeline

`RunPersistenceService` принимает существующий `PipelineRun` и результат
`FullPipelineService`. Он не запускает pipeline, не обучает модели и не считает
metrics. Его задача только сохранить metadata в Django models:

- `DatasetArtifact` для processed dataset;
- `DatasetArtifact` для final dataset;
- `ModelArtifact` и `MetricSnapshot` для dummy baseline, если dummy обучался;
- `ModelArtifact` и `MetricSnapshot` для baseline, если baseline обучался;
- `ModelArtifact` и `MetricSnapshot` для CatBoost, если CatBoost обучался;
- `ReportArtifact` для `target_distribution`, если `FullPipelineService` создал
  PNG-отчет;
- `ReportArtifact` для `metrics_plot`, если был хотя бы один model result;
- `ReportArtifact` для `stability_table`, если были test predictions;
- `ReportArtifact` для `stability_plot`, если были test predictions;
- `ReportArtifact` для `feature_importance`, если CatBoost обучался и вернул
  feature importances.

Эти значения явно отражены в Django `TextChoices`: `ModelArtifact.ModelType`
содержит `dummy`, `baseline`, `catboost`, а `ReportArtifact.ReportType`
содержит `target_distribution`, `metrics_plot`, `feature_importance`,
`stability_table`, `stability_plot`, `forecast_replay` и
`forecast_replay_table`.

Если у метрики `roc_auc` значение `None`, metrics comparison report не падает:
на PNG это место подписывается как `N/A`.
Если CatBoost выключен или importances пустые, feature importance report не
создается.

Сервис использует `transaction.atomic()`, чтобы связанные metadata-записи
создавались одной транзакцией.

Для `file_path` действует такое правило: если путь абсолютный и лежит внутри
`MEDIA_ROOT`, сохраняется путь относительно `MEDIA_ROOT`; иначе сохраняется
строковое представление пути как есть.

## Как RunPipelineUseCase управляет одним запуском

`RunPipelineUseCase` связывает `PipelineRun`, raw `DataFrame`,
`FullPipelineService` и `RunPersistenceService`.

Сценарий такой:

1. Перевести `PipelineRun.status` в `running`.
2. Заполнить `started_at` и очистить `error_message`.
3. Запустить `FullPipelineService`.
4. Сохранить artifacts и metrics metadata через `RunPersistenceService`.
5. Перевести `PipelineRun.status` в `success` и заполнить `finished_at`.

Если внутри pipeline возникает ошибка, use case переводит run в `failed`,
записывает короткий текст ошибки в `error_message`, заполняет `finished_at` и
повторно выбрасывает исключение.

`RunPipelineUseCase` сам не скачивает данные. CSV и Binance входы сначала
получают raw `DataFrame`, а потом передают его в этот use case.

## Как вручную загрузить OHLCV candles из Binance

`BinanceMarketDataProvider` находится в `mlcore.loaders.binance_loader`.
Он использует Binance Spot REST endpoint `/api/v3/klines`, поддерживает
пагинацию по 1000 candles за запрос и возвращает pandas `DataFrame` с колонками:

- `timestamp`;
- `open`;
- `high`;
- `low`;
- `close`;
- `volume`;
- `symbol`.

`timestamp` приводится к datetime, а OHLCV-колонки - к numeric.

Пример ручного использования из Python:

```python
from mlcore.loaders import BinanceMarketDataProvider

provider = BinanceMarketDataProvider()
df = provider.get_ohlcv(
    symbol="BTCUSDT",
    interval="1h",
    start="2024-01-01",
    end="2024-01-05",
)
print(df.head())
```

Provider только загружает данные. Он не создает `PipelineRun`, не сохраняет
datasets и не запускает обучение. Ошибки Binance API, пустой ответ и network
ошибки превращаются в понятный `BinanceMarketDataError`.

## Как вручную проверить CatBoostTrainingService

`CatBoostTrainingService` запускается похожим образом, но сохраняет модель в
CatBoost native `.cbm` формате. Для ручной проверки удобно передать
`CatBoostTrainer(iterations=5, verbose=False)`, чтобы обучение было быстрым.

```powershell
.crypto\Scripts\python.exe -c "from pathlib import Path; import pandas as pd; from mlcore.repositories import ArtifactRepository; from mlcore.services import CatBoostTrainingService; from mlcore.training import CatBoostTrainer; df = pd.DataFrame({'timestamp': pd.date_range('2024-01-01', periods=80, freq='h'), 'symbol': ['BTCUSDT'] * 80, 'feature_1': range(80), 'feature_2': [i % 5 for i in range(80)], 'target': [i % 2 for i in range(80)]}); service = CatBoostTrainingService(artifact_repository=ArtifactRepository(Path('tmp_artifacts/manual_catboost_check')), trainer=CatBoostTrainer(iterations=5, verbose=False)); result = service.train_and_evaluate(df, run_id=1); print('model_path=', result.model_path); print('metrics=', result.metrics); print('features=', result.feature_columns); print('rows=', result.train_rows, result.valid_rows, result.test_rows)"
```

Ожидаемый смысл результата:

- `model_path` показывает путь к сохраненному `.cbm` файлу;
- `metrics` содержит `accuracy`, `precision`, `recall`, `f1`, `roc_auc`,
  `confusion_matrix`;
- `features` показывает numeric feature columns, которые использовала модель;
- `rows` показывает размеры train, valid и test частей.

## Где лежат datasets, models и reports

Большие файлы должны храниться в `media/`:

```text
media/
  datasets/
    raw/
    processed/
    final/
  models/
  reports/
```

Назначение папок:

- `media/datasets/raw/` - сырые OHLCV-данные, включая uploaded CSV из `/upload/`;
- `media/datasets/processed/` - очищенные или промежуточные datasets;
- `media/datasets/final/` - финальные datasets с features и target;
- `media/models/` - trained model artifacts;
- `media/reports/` - plots, metrics JSON, markdown reports и другие reports.

`DatasetRepository` умеет сохранять и читать `.csv` и `.parquet`.
`ModelRepository` умеет сохранять и читать `.joblib`, `.pkl` и `.cbm`.
`ArtifactRepository` строит безопасные пути для datasets, models и reports.

## Почему SQLite хранит только metadata

SQLite подходит для небольших записей:

- параметры запуска;
- статус запуска;
- даты создания, старта и окончания;
- пути к artifacts;
- row counts;
- metrics snapshots;
- error message.

Большие datasets, trained models и plots не нужно класть внутрь SQLite.
Если хранить большие файлы прямо в базе, база быстро станет тяжелой, медленной
и неудобной для backup/debug.

Поэтому SQLite хранит только описание и ссылки, а сами файлы лежат в `media/`.

## Какие команды нужны чаще всего

Проверить Django:

```powershell
.crypto\Scripts\python.exe manage.py check
```

Запустить сервер:

```powershell
.crypto\Scripts\python.exe manage.py runserver
```

Запустить tests:

```powershell
.crypto\Scripts\python.exe manage.py test
```

Запустить Ruff lint:

```powershell
.crypto\Scripts\python.exe -m ruff check .
```

Проверить Ruff formatting:

```powershell
.crypto\Scripts\python.exe -m ruff format --check .
```

Создать admin user:

```powershell
.crypto\Scripts\python.exe manage.py createsuperuser
```

Применить migrations на свежей базе:

```powershell
.crypto\Scripts\python.exe manage.py migrate
```

Открыть основные страницы:

```text
http://127.0.0.1:8000/
http://127.0.0.1:8000/runs/
http://127.0.0.1:8000/admin/
```

## Current limitations

- CSV upload, Binance page и CLI commands запускают pipeline синхронно, без async queue.
- Dashboard является read-only overview page и не создает `PipelineRun`.
- Для запуска pipeline используйте `/binance/`, `/upload/`, `run_csv_pipeline`
  или `run_binance_pipeline`.
