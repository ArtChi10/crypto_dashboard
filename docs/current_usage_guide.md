# Current usage guide

Это руководство описывает текущее состояние проекта `crypto_dashboard`.
Оно не описывает будущую версию и не обещает функциональность, которой пока
нет в коде.

## Что это за проект

`crypto_dashboard` - это Django-приложение для учета запусков ML-пайплайна,
который должен прогнозировать направление цены криптовалют.

Сейчас проект умеет хранить metadata о запусках, показывать простые страницы
Dashboard и Runs, создавать запись `PipelineRun` через UI, хранить ссылки на
dataset/model/report artifacts и запускать отдельные ML-компоненты из Python.

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
- Форма создания `PipelineRun` на главной странице.
- `ArtifactRepository` для построения путей artifacts.
- `DatasetRepository` для сохранения и загрузки `.csv` и `.parquet`.
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

## Что еще не работает

- Нет загрузчика данных из Binance.
- Нет кнопки UI, которая запускает полный pipeline.
- Нет полного pipeline через UI.
- Форма на главной странице создает только metadata-запись `PipelineRun`.
- Чекбоксы `Train baseline` и `Train main model` пока не запускают обучение.
- Реальные metrics в UI пока не записываются автоматически.
- Model artifacts через UI пока не создаются.

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

Важно: сейчас UI не скачивает данные, не строит features, не обучает модель и
не записывает metrics. Он создает metadata-запись запуска.

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
`BaselineTrainingService` и `CatBoostTrainingService`.

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

- `media/datasets/raw/` - сырые OHLCV-данные;
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

- Binance download еще нет.
- Full pipeline button еще нет.
- Full pipeline через UI еще не реализован.
- Реальные metrics в UI пока не пишутся автоматически.
- Model artifacts через UI пока не создаются.
- Чекбоксы `Train baseline` и `Train main model` пока не запускают обучение.
- `DatasetPreparationService` можно запускать вручную из Python, но UI пока не
  вызывает его автоматически.
- `BaselineTrainingService` можно запускать вручную из Python, но UI пока не
  вызывает его автоматически.
- `CatBoostTrainingService` можно запускать вручную из Python, но UI пока не
  вызывает его автоматически.
