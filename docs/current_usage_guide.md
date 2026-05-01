# Current usage guide

Это руководство описывает текущее состояние проекта `crypto_dashboard`.
Оно не описывает будущую версию и не обещает функциональность, которой пока
нет в коде.

## Что это за проект

`crypto_dashboard` - это Django-приложение для учета запусков ML-пайплайна,
который должен прогнозировать направление цены криптовалют.

Сейчас проект умеет хранить metadata о запусках, показывать простые страницы
Dashboard и Runs, создавать запись `PipelineRun` через UI, загружать raw OHLCV
CSV через `/upload/`, хранить ссылки на dataset/model/report artifacts и
запускать отдельные ML-компоненты из Python.

Research report skeleton: [`docs/research_report.md`](research_report.md).

Главное правило хранения:

```text
SQLite = metadata only
media/ = большие файлы datasets, models, reports
```

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
- Минимальный общий UI layout и CSS для Dashboard, Upload и Runs pages.
- Форма создания `PipelineRun` на главной странице.
- Страница `/upload/` для ручной загрузки raw OHLCV CSV, сохранения raw artifact
  и синхронного запуска pipeline.
- Страница `/binance/` для загрузки OHLCV candles из Binance и синхронного
  запуска pipeline.
- `ArtifactRepository` для построения путей artifacts.
- `DatasetRepository` для сохранения и загрузки `.csv` и `.parquet`.
- `BinanceMarketDataProvider` для загрузки OHLCV candles из Binance Spot REST API
  в pandas `DataFrame`.
- `DataCleaner` для очистки OHLCV-данных.
- `FeatureBuilder` для построения признаков.
- `TargetBuilder` для построения target-колонки.
- `DatasetPreparationService` для ручной подготовки processed/final datasets из Python.
- `SplitService` для временного train/valid/test split.
- `Evaluator` для расчета classification metrics.
- `BaselineTrainer` на базе `LogisticRegression`.
- `CatBoostTrainer`.
- `ModelRepository` для сохранения и загрузки `.joblib`, `.pkl`, `.cbm`.
- `BaselineTrainingService` для ручного обучения baseline-модели из Python.
- `CatBoostTrainingService` для ручного обучения CatBoost-модели из Python.
- `TargetDistributionReportService` для PNG-отчета распределения target.
- `MetricsComparisonReportService` для PNG-сравнения metrics по моделям.
- `FeatureImportanceReportService` для PNG-отчета важности CatBoost-признаков.
- `FullPipelineService` для ручного in-memory запуска preparation + training из Python.
- `RunPersistenceService` для сохранения результатов pipeline в Django metadata.
- `RunPipelineUseCase` для orchestration одного `PipelineRun` из Python.
- `CsvPipelineUploadUseCase` для orchestration ручной CSV-загрузки из UI и CLI.
- Management command `run_csv_pipeline` для запуска pipeline из CSV через CLI.
- Management command `run_binance_pipeline` для загрузки Binance OHLCV и запуска
  pipeline через CLI.

## Что еще не работает

- Форма на главной странице создает только metadata-запись `PipelineRun`.
- Чекбоксы `Train baseline` и `Train main model` пока не запускают обучение.
- Главная форма не запускает полный pipeline; для ручного запуска используйте
  `/binance/` или `/upload/`.
- Нет async/background queue: CSV upload и Binance page запускают pipeline
  синхронно.

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
.crypto\Scripts\python.exe -m unittest discover
```

Что делают команды:

- `manage.py check` проверяет Django-настройки и конфигурацию проекта.
- `ruff check .` запускает lint-проверку Python-кода.
- `ruff format --check .` проверяет форматирование без изменения файлов.
- `unittest discover` запускает unit tests.

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
- ссылка на историю `/runs/`;
- ссылка на ручную загрузку `/upload/`;
- форма создания нового `PipelineRun`;
- таблица последних запусков.

## Как создать PipelineRun через UI

1. Откройте Dashboard:

```text
http://127.0.0.1:8000/
```

2. Заполните форму:

- `Symbols`: тикеры через запятую, например `BTCUSDT, ETHUSDT`;
- `Interval`: интервал свечей, например `1h`;
- `Start date`: начальная дата;
- `End date`: конечная дата;
- `Target horizon`: горизонт прогноза, например `3`;
- `Train baseline`: сейчас чекбокс есть в форме, но обучение не запускает;
- `Train main model`: сейчас чекбокс есть в форме, но обучение не запускает.

3. Нажмите `Создать запуск`.

После отправки формы Django создаст запись `PipelineRun` со статусом `Created`
и перенаправит на страницу `/runs/<id>/`.

Важно: эта Dashboard-форма не скачивает данные, не строит features, не обучает
модель и не записывает metrics. Она создает metadata-запись запуска.

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
- `train_catboost`.

3. Нажмите `Скачать Binance data и запустить pipeline`.

После отправки формы view вызывает `BinancePipelineUseCase`. Этот use case
скачивает OHLCV через `BinanceMarketDataProvider`, сохраняет raw Binance dataset
как parquet `DatasetArtifact(type="raw")`, запускает `RunPipelineUseCase` и
перенаправляет на `/runs/<id>/`.

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
- создаются baseline и CatBoost model artifacts;
- создаются `MetricSnapshot` для моделей;
- создаются PNG reports: target distribution, metrics comparison и CatBoost
  feature importance;
- detail page `/runs/<id>/` показывает artifacts, metrics и inline PNG reports.

Важно: высокие metrics на коротком периоде не доказывают рыночную
предсказательность. Это research/MVP pipeline для воспроизводимых экспериментов,
а не production trading system.

## Как запустить raw CSV pipeline из CLI

Management command использует тот же `CsvPipelineUploadUseCase`, что и страница
`/upload/`. Команда не дублирует pipeline-логику, а только проверяет CLI-аргументы
и передает CSV-файл в use case.

Пример:

```powershell
.crypto\Scripts\python.exe manage.py run_csv_pipeline --csv tmp_cli_check/input.csv --symbol BTCUSDT --interval 1h --start-date 2024-01-01 --end-date 2024-01-05 --target-horizon 3
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

## Как открыть /runs/ и /runs/<id>/

История запусков:

```text
http://127.0.0.1:8000/runs/
```

На странице `/runs/` отображается таблица `PipelineRun` с пагинацией по 25
записей на страницу.

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

Для artifacts, которые лежат внутри `MEDIA_ROOT`, `file_path` показывается как
ссылка вида `/media/...`. Для model artifacts страница выводит summary из
`params_json`: `train_rows`, `valid_rows`, `test_rows` и `feature_count`.
Classification metrics округляются до 4 знаков, а confusion matrix показывается
в читаемом виде. PNG-файлы `ReportArtifact` из `media/reports/` дополнительно
показываются прямо на странице как inline images; ссылка на файл при этом
остается кликабельной. Non-PNG reports и небезопасные пути отображаются без
inline image.

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

## Как запустить unit tests

```powershell
.crypto\Scripts\python.exe -m unittest discover
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

## Как вручную проверить FullPipelineService

`FullPipelineService` запускает весь текущий ML-сценарий на переданном raw
`DataFrame`: подготовку датасета, загрузку final parquet и обучение выбранных
моделей. Он не пишет metadata в SQLite и не создает Django artifacts.

Для synthetic данных важно, чтобы после `TargetBuilder` получались оба класса
`target`, иначе trainers честно откажутся обучаться на одном классе.

```powershell
.crypto\Scripts\python.exe -c "from pathlib import Path; import pandas as pd; from mlcore.repositories import ArtifactRepository; from mlcore.services import CatBoostTrainingService, FullPipelineService; from mlcore.training import CatBoostTrainer; close = [1, 3, 2, 4] * 25; df = pd.DataFrame({'timestamp': pd.date_range('2024-01-01', periods=100, freq='h'), 'open': close, 'high': [x + 1 for x in close], 'low': [x - 1 for x in close], 'close': close, 'volume': range(100, 200), 'symbol': ['BTCUSDT'] * 100}); artifact_repo = ArtifactRepository(Path('tmp_artifacts/manual_full_pipeline_check')); service = FullPipelineService(catboost_training_service=CatBoostTrainingService(artifact_repository=artifact_repo, trainer=CatBoostTrainer(iterations=5, verbose=False))); result = service.run(df, run_id=1, horizon=3, symbol='BTCUSDT'); print('final_path=', result.preparation_result.final_path); print('baseline=', result.baseline_result is not None); print('catboost=', result.catboost_result is not None); print('baseline_metrics=', result.baseline_result.metrics); print('catboost_metrics=', result.catboost_result.metrics)"
```

Ожидаемый смысл результата:

- `final_path` показывает путь к сохраненному final parquet dataset;
- `baseline=True` означает, что baseline-модель обучилась и сохранилась;
- `catboost=True` означает, что CatBoost-модель обучилась и сохранилась;
- `baseline_metrics` и `catboost_metrics` содержат classification metrics.

## Как сохранять metadata результата pipeline

`RunPersistenceService` принимает существующий `PipelineRun` и результат
`FullPipelineService`. Он не запускает pipeline, не обучает модели и не считает
metrics. Его задача только сохранить metadata в Django models:

- `DatasetArtifact` для processed dataset;
- `DatasetArtifact` для final dataset;
- `ModelArtifact` и `MetricSnapshot` для baseline, если baseline обучался;
- `ModelArtifact` и `MetricSnapshot` для CatBoost, если CatBoost обучался;
- `ReportArtifact` для `target_distribution`, если `FullPipelineService` создал
  PNG-отчет;
- `ReportArtifact` для `metrics_plot`, если был хотя бы один model result;
- `ReportArtifact` для `feature_importance`, если CatBoost обучался и вернул
  feature importances.

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
.crypto\Scripts\python.exe -m unittest discover
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

- Binance provider уже подключен к CLI command `run_binance_pipeline` и странице
  `/binance/`, но пока не подключен к основной Dashboard-форме.
- Реальные metrics для metadata-only формы на Dashboard пока не пишутся автоматически.
- Чекбоксы `Train baseline` и `Train main model` пока не запускают обучение.
- Главная Dashboard-форма остается metadata-only.
- CSV upload, Binance page и CLI commands запускают pipeline синхронно, без async queue.
- `CsvPipelineUploadUseCase` подключен к `/upload/` и `run_csv_pipeline`, но не к
  основной Dashboard-форме.
