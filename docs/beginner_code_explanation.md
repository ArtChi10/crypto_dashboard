# Beginner code explanation

Этот документ объясняет код проекта `crypto_dashboard` простыми словами.
Представьте, что проект - это журнал лабораторных опытов по ML: мы записываем,
какой опыт хотели запустить, какие данные использовали, какую модель обучили и
какие результаты получили.

## Что такое Django в этом проекте

Django - это каркас веб-приложения.

В этом проекте Django отвечает за:

- страницы в браузере;
- формы реального запуска pipeline через Binance или CSV;
- admin-панель;
- Django database;
- models, то есть таблицы metadata.

Django здесь не обучает модель сам. Он дает удобную оболочку: где посмотреть
запуски, где запустить pipeline через UI и где хранить metadata.

## Зачем нужны apps dashboard и runs

В Django проект обычно делят на apps. App - это отдельная часть проекта со
своей задачей.

`dashboard` отвечает за главную страницу `/`.

На ней есть:

- краткий статус;
- короткое объяснение проекта;
- ссылка на запуск Binance pipeline `/binance/`;
- ссылка на ручную загрузку raw CSV `/upload/`;
- ссылка на историю запусков `/runs/`;
- список последних запусков.

`runs` отвечает за страницы запусков:

- `/runs/` - список всех запусков;
- `/runs/<id>/` - детали одного запуска.

На pipeline pages есть короткие contextual help-блоки. Они не запускают код и не
меняют данные; это обычный template text, который объясняет входные данные,
статусы, artifacts, metrics и reports.

Так проще поддерживать код: главная страница живет в одном месте, история и
детали запусков - в другом.

## Что такое PipelineRun

`PipelineRun` - это запись о попытке запустить ML-пайплайн.

Можно думать о нем как о карточке задачи:

- какие symbols выбрали, например `BTCUSDT`;
- какой interval выбрали, например `1h`;
- какие даты выбрали;
- какой `target_horizon` выбрали;
- какой статус у запуска;
- когда запуск создан;
- когда он стартовал и закончился;
- была ли ошибка.

Главная страница больше не создает пустой `PipelineRun`. Это обзорная страница:
она показывает ссылки на настоящие entry points и последние запуски.

Для ручного запуска pipeline через UI есть отдельные страницы:

- `/binance/` - скачивает raw OHLCV из Binance через `BinancePipelineUseCase`;
- `/upload/` - принимает raw OHLCV CSV, сохраняет исходный CSV как raw
  `DatasetArtifact` и запускает pipeline через `CsvPipelineUploadUseCase`.

Обе страницы показывают результат на странице запуска `/runs/<id>/`.

## Что такое ArtifactRepository

`ArtifactRepository` строит правильные пути для файлов.

Например, если нужно сохранить raw dataset для run `12`, repository сделает
понятный путь вроде:

```text
media/datasets/raw/raw_run_12_BTCUSDT_20260427_120501.csv
```

Он следит, чтобы:

- dataset artifacts попадали в `datasets/raw`, `datasets/processed` или
  `datasets/final`;
- model artifacts попадали в `models`;
- report artifacts попадали в `reports`;
- имена файлов были предсказуемыми.

Новые stability reports тоже строят paths через `ArtifactRepository`:

- `stability_table` - CSV table;
- `stability_plot` - PNG chart.

Это похоже на библиотекаря, который знает, на какую полку поставить каждую
книгу.

## Что такое DatasetRepository

`DatasetRepository` сохраняет и загружает таблицы с данными.

Он работает с pandas `DataFrame` и поддерживает:

- `.csv`;
- `.parquet`.

Если дать ему путь к `.parquet`, он сохранит или прочитает parquet.
Если дать путь к `.csv`, он сохранит или прочитает csv.
Если дать другой формат, например `.json`, он скажет, что такой формат не
поддерживается.

## Что делает DataCleaner

`DataCleaner` чистит сырые OHLCV-данные.

OHLCV - это обычные свечные данные:

- `open`;
- `high`;
- `low`;
- `close`;
- `volume`;
- `timestamp`;
- `symbol`.

`DataCleaner` делает несколько простых, но важных вещей:

- проверяет, что нужные колонки есть;
- превращает `timestamp` в дату и время;
- превращает цены и volume в числа;
- удаляет строки без нормального `timestamp` или `close`;
- удаляет дубликаты по `symbol` и `timestamp`;
- сортирует данные по `symbol` и времени;
- убирает строки с отрицательным `volume`.

Идея простая: перед обучением модели данные должны быть аккуратными.

## Что делает FeatureBuilder

`FeatureBuilder` добавляет признаки.

Признаки - это подсказки для модели. Модель не должна смотреть только на цену
`close`; ей полезны дополнительные числа.

`FeatureBuilder` добавляет, например:

- доходность за 1, 3, 6 и 12 шагов;
- moving average за 7 и 14 шагов;
- exponential moving average за 7 и 30 шагов;
- volatility за 7 и 14 шагов;
- изменение volume;
- moving average для volume;
- размер тела свечи;
- диапазон свечи.

После построения признаков строки, где признаков еще не хватает, удаляются.
Например, moving average за 14 шагов нельзя честно посчитать на самой первой
строке.

## Что делает TargetBuilder

`TargetBuilder` создает колонку `target`.

`target` - это ответ, который модель должна научиться предсказывать.

В этом проекте target простой:

```text
1, если цена close через horizon шагов выше текущей
0, если не выше
```

Например, если `horizon = 3`, код смотрит на цену через 3 свечи.
Если будущая цена выше текущей, target будет `1`.
Иначе target будет `0`.

Последние строки удаляются, потому что для них еще нет будущей цены.

## Что делает DatasetPreparationService

`DatasetPreparationService` соединяет подготовку датасета в один ручной
сценарий для Python-кода.

Он делает так:

1. Получает raw OHLCV `DataFrame`.
2. Чистит его через `DataCleaner`.
3. Сохраняет processed dataset в parquet через `DatasetRepository`.
4. Строит features через `FeatureBuilder`.
5. Строит `target` через `TargetBuilder`.
6. Сохраняет final dataset в parquet через `DatasetRepository`.
7. Возвращает результат: пути к processed/final файлам, количество строк,
   feature columns и имя target column.

Важно: этот service не скачивает данные, не обучает модели и не пишет metadata
в SQLite. Он только готовит файлы датасетов.

## Зачем нужен SplitService

`SplitService` делит dataset на три части:

- train;
- valid;
- test.

Train нужен, чтобы модель училась.
Valid нужен, чтобы проверять модель во время настройки.
Test нужен, чтобы честно оценить результат на данных, которые модель не видела.

Важно: `SplitService` сортирует данные по времени и не перемешивает их.

## Почему нельзя перемешивать временные данные

Криптовалютные свечи - это временной ряд.
Временной ряд похож на дневник: сначала идет понедельник, потом вторник, потом
среда.

Если перемешать строки случайно, модель может случайно увидеть кусочек будущего
во время обучения. Тогда оценка станет слишком красивой, но нечестной.

Для прогнозирования цены нужно учиться на прошлом и проверяться на будущем.
Поэтому данные делятся по времени:

```text
старые данные -> train
средние данные -> valid
новые данные -> test
```

## Что делает WalkForwardValidationService

`WalkForwardValidationService` нужен для research-проверки временных рядов более
строгим способом, чем один holdout split.

Он строит несколько последовательных folds:

```text
fold 1: train старое окно -> test следующее окно
fold 2: train следующее окно -> test следующее окно
fold 3: ...
```

Окна задаются количеством строк: `train_window`, `test_window` и `step`.
Например, при `train_window=100`, `test_window=20` и `step=20` service сначала
берет первые 100 строк для train, следующие 20 для test, потом сдвигается на 20
строк и повторяет.

Важно: service сортирует данные по `timestamp`, не делает random shuffle и
возвращает copies с reset index.

## Что делает WalkForwardEvaluationService

`WalkForwardEvaluationService` делает следующий шаг после
`WalkForwardValidationService`: он не только строит folds, но и проверяет модель
на каждом fold.

Для каждого fold он:

1. Берет feature columns через `trainer.get_feature_columns(...)`, если такой
   метод есть.
2. Если такого метода нет, выбирает numeric columns и исключает `target`,
   `timestamp` и `symbol`.
3. Обучает trainer на train-части fold.
4. Делает `predict` на test-части.
5. Если модель умеет `predict_proba`, передает вероятности в `Evaluator`.
6. Возвращает таблицу с `fold_id`, границами train/test окна, количеством строк
   и metrics.

Если обучение на отдельном fold падает, например из-за одного класса в
`y_train`, service по умолчанию не останавливает весь анализ. Он записывает
`error_message`, а metrics оставляет пустыми. Если нужно строгое поведение,
можно передать `raise_on_error=True`.

Сейчас это research utility: он не сохраняет artifacts, не пишет в Django DB и
не подключен к основному pipeline/UI.

## Что делает FeatureAblationService

`FeatureAblationService` помогает понять, какие группы признаков дают вклад в
качество модели.

Сейчас есть стандартные группы:

- `price_raw`: `open`, `high`, `low`, `close`;
- `returns`: `return_1`, `return_3`, `return_6`, `return_12`;
- `moving_average`: `ma_7`, `ma_14`, `ema_7`, `ema_30`;
- `volatility`: `volatility_7`, `volatility_14`;
- `volume`: `volume`, `volume_change`, `volume_ma_7`;
- `candle`: `candle_body`, `candle_range`.

В основном режиме service сначала обучает модель на `all_features`, а потом
повторяет experiment без каждой группы:

```text
all_features
without_price_raw
without_returns
without_moving_average
...
```

Для каждого experiment вызывается `trainer_factory`, поэтому модель создается
заново и результаты не смешиваются между experiments. Если какая-то группа
отсутствует в dataset, service возвращает row с `error_message`, а не ломает
весь анализ.

Сейчас это ручной research-инструмент: он не сохраняет artifacts, не пишет в
Django DB и не подключен к основному pipeline/UI.

## Что делает Evaluator

`Evaluator` считает качество модели.

Он умеет считать:

- `accuracy`;
- `precision`;
- `recall`;
- `f1`;
- `roc_auc`;
- `confusion_matrix`.

Если модель умеет выдавать вероятности через `predict_proba`, evaluator может
посчитать `roc_auc`. Если вероятностей нет или в ответах только один класс,
`roc_auc` будет `None`.

## Что делает PeriodStabilityAnalysisService

`PeriodStabilityAnalysisService` помогает понять, насколько metrics стабильны
во времени.

Он не обучает модель и не запускает pipeline. Вместо этого он берет уже готовую
таблицу predictions:

- `timestamp`;
- `y_true`;
- `y_pred`;
- `y_proba`, если есть.

Потом service группирует строки по периоду, например по дням (`period="D"`) или
неделям (`period="W"`), и для каждого периода снова вызывает `Evaluator`.

На выходе получается pandas `DataFrame`, где каждая строка - отдельный временной
сегмент:

- `period_start`;
- `period_end`;
- `rows`;
- `positive_rate`;
- `accuracy`;
- `precision`;
- `recall`;
- `f1`;
- `roc_auc`.

Если в периоде только один класс или нет `y_proba`, `roc_auc` будет `None`.
В полном pipeline этот анализ уже используется через `PeriodStabilityReportService`:
сохраняется CSV-таблица `stability_table` и PNG-график `stability_plot`.

## Что делает PeriodStabilityReportService

`PeriodStabilityReportService` берет test predictions нескольких моделей:

- dummy;
- baseline;
- CatBoost.

Для каждой модели он вызывает `PeriodStabilityAnalysisService`, объединяет
результаты в одну таблицу и сохраняет CSV. Дополнительно строится PNG-график
`accuracy`, `f1` и `roc_auc` по времени.

Это уже интегрировано в `FullPipelineService`: если training services вернули
test predictions, pipeline создает stability reports в `media/reports/`.

## Что такое BaselineTrainer

`BaselineTrainer` обучает простую базовую модель.

Сейчас это pipeline из:

- `StandardScaler`;
- `LogisticRegression`.

Baseline нужен как сильнее устроенная первая точка сравнения. CatBoost можно
сравнивать с этим baseline и с совсем наивным dummy baseline.

`BaselineTrainer` берет только numeric feature columns и не использует:

- `target`;
- `timestamp`;
- `symbol`.

## Что такое DummyBaselineTrainer

`DummyBaselineTrainer` обучает `sklearn.dummy.DummyClassifier`.

По умолчанию используется `strategy="most_frequent"`: модель всегда предсказывает
самый частый класс из train split. Это не попытка найти рыночный сигнал, а
наивная research-точка сравнения.

В отличие от LogisticRegression и CatBoost, dummy baseline разрешает one-class
`y_train`. Это сделано специально: наивный baseline должен показывать, что
получится даже в вырожденном случае.

## Что такое CatBoostTrainer

`CatBoostTrainer` обучает `CatBoostClassifier`.

Он уже реализован как trainer: его можно вызвать из Python-кода и передать ему
train/valid данные.

Важно: `CatBoostTrainer` - это низкоуровневый trainer. Он умеет обучить модель,
но сам не делает split, не считает metrics и не сохраняет artifact.

Для полного ручного сценария из Python теперь есть `CatBoostTrainingService`.
Страница `/upload/` может запустить CatBoost training через общий
`RunPipelineUseCase`.

## Что такое ModelRepository

`ModelRepository` сохраняет и загружает обученные модели.

Он поддерживает:

- `.joblib`;
- `.pkl`;
- `.cbm`.

Обычные Python-модели сохраняются через `joblib`.
CatBoost `.cbm` сохраняется через native метод CatBoost `save_model`.

## Что делает BaselineTrainingService

`BaselineTrainingService` соединяет несколько деталей в один ручной сценарий:

1. Проверяет, что в dataset есть колонка `target`.
2. Находит numeric feature columns.
3. Делит данные через `SplitService`.
4. Обучает baseline через `BaselineTrainer`.
5. Считает metrics через `Evaluator`.
6. Строит путь к model artifact через `ArtifactRepository`.
7. Сохраняет модель через `ModelRepository`.
8. Возвращает результат: путь к модели, metrics, features и размеры split.

Это уже рабочий service для Python-кода.

Сам по себе service не вызывается из Dashboard напрямую. В UI его запускает
общий `RunPipelineUseCase` через страницы `/upload/` и `/binance/`.

## Что делает DummyTrainingService

`DummyTrainingService` похож на `BaselineTrainingService`, но обучает
`DummyBaselineTrainer`.

Он делает time-based split, обучает naive baseline, считает metrics через
`Evaluator`, сохраняет модель как `.joblib` и возвращает размеры split.

В полном pipeline dummy baseline включен по умолчанию, чтобы metrics comparison
всегда содержал тривиальную точку сравнения.

## Что делает CatBoostTrainingService

`CatBoostTrainingService` похож на `BaselineTrainingService`, но вместо
baseline-модели обучает `CatBoostClassifier`.

Он делает тот же application-level сценарий:

1. Проверяет, что в dataset есть колонка `target`.
2. Находит numeric feature columns.
3. Делит данные через `SplitService`.
4. Обучает CatBoost через `CatBoostTrainer` на train и valid split.
5. Считает metrics через `Evaluator`.
6. Строит путь к `.cbm` model artifact через `ArtifactRepository`.
7. Сохраняет модель через `ModelRepository`.
8. Возвращает путь к модели, metrics, features и размеры split.

Это уже рабочий service для Python-кода.

Сам по себе service не вызывается из Dashboard напрямую. В UI его запускает
общий `RunPipelineUseCase` через страницы `/upload/` и `/binance/`.

## Что делает FullPipelineService

`FullPipelineService` - это верхний ручной service для in-memory запуска
текущего ML-пайплайна.

Он получает raw OHLCV `DataFrame` и делает так:

1. Запускает `DatasetPreparationService`.
2. Загружает final parquet dataset через `DatasetRepository`.
3. Строит PNG report распределения `target` через `TargetDistributionReportService`.
4. Если включен `train_dummy`, запускает `DummyTrainingService`.
5. Если включен `train_baseline`, запускает `BaselineTrainingService`.
6. Если включен `train_catboost`, запускает `CatBoostTrainingService`.
7. Если есть хотя бы один model result, строит PNG comparison report через
   `MetricsComparisonReportService`.
8. Если есть test predictions, строит CSV/PNG stability reports через
   `PeriodStabilityReportService`.
9. Если CatBoost вернул feature importances, строит PNG feature importance report
   через `FeatureImportanceReportService`.
10. Возвращает общий результат: preparation result, dummy result, baseline result,
    CatBoost result и paths к report files.

Если все training flags выключены, service сразу выдаст `ValueError`.

Важно: это еще не Django runner. Он не пишет `PipelineRun`, `DatasetArtifact`,
`MetricSnapshot` или `ModelArtifact` в SQLite. Он только связывает уже готовые
ML-компоненты в один Python-сценарий.

## Что делает RunPersistenceService

`RunPersistenceService` - это тонкий мост между ML-результатом и Django
metadata.

Он получает:

- уже существующий `PipelineRun`;
- результат `FullPipelineService`.

После этого он создает metadata-записи:

- `DatasetArtifact` для processed dataset;
- `DatasetArtifact` для final dataset;
- `ModelArtifact` для dummy baseline, если dummy запускался;
- `MetricSnapshot` для dummy baseline, если dummy запускался;
- `ModelArtifact` для baseline, если baseline запускался;
- `MetricSnapshot` для baseline, если baseline запускался;
- `ModelArtifact` для CatBoost, если CatBoost запускался;
- `MetricSnapshot` для CatBoost, если CatBoost запускался;
- `ReportArtifact` для target distribution PNG;
- `ReportArtifact` для metrics comparison PNG;
- `ReportArtifact` для stability table CSV;
- `ReportArtifact` для stability plot PNG;
- `ReportArtifact` для CatBoost feature importance PNG.

В `runs/models.py` эти типы теперь записаны явно в Django choices:
`ModelArtifact.ModelType` знает `dummy`, `baseline`, `catboost`, а
`ReportArtifact.ReportType` знает `target_distribution`, `metrics_plot`,
`feature_importance`, `stability_table` и `stability_plot`. Это помогает admin,
forms и будущему коду показывать те же значения, которые реально сохраняет
pipeline.

Если `roc_auc` равен `None`, metrics comparison PNG не падает: это значение
показывается как `N/A`.
Если CatBoost выключен или importances пустые, feature importance PNG не
создается.

Он не обучает модели, не строит признаки, не скачивает данные и не меняет UI.
Он только записывает в Django DB ссылки на уже созданные файлы и уже посчитанные
metrics.

Если путь к файлу абсолютный и находится внутри `MEDIA_ROOT`, service сохраняет
его относительно `MEDIA_ROOT`. Остальные пути сохраняются строкой как есть.

## Что делает RunPipelineUseCase

`RunPipelineUseCase` - это сценарий одного запуска `PipelineRun`.

Он соединяет:

- запись `PipelineRun` из Django;
- raw OHLCV `DataFrame`;
- `FullPipelineService`;
- `RunPersistenceService`.

Когда все хорошо, он делает так:

1. Ставит run в статус `running`.
2. Записывает `started_at`.
3. Очищает старый `error_message`.
4. Запускает полный pipeline.
5. Сохраняет metadata artifacts и metrics.
6. Ставит run в статус `success`.
7. Записывает `finished_at`.

Если что-то падает, он ставит run в статус `failed`, записывает короткую ошибку
в `error_message`, заполняет `finished_at` и снова выбрасывает ошибку. Так код,
который вызвал use case, видит проблему, а в базе остается понятный failed run.

Важно: use case не скачивает данные из Binance. Страница `/upload/` читает CSV
в raw `DataFrame` и передает его в этот use case. Binance-загрузка теперь есть
отдельным provider-ом, но пока не подключена к этому use case.

## Что делает BinanceMarketDataProvider

`BinanceMarketDataProvider` находится в `mlcore/loaders/binance_loader.py`.

Это infrastructure-компонент для Binance Spot REST API. Он обращается к endpoint
`/api/v3/klines`, загружает candles и возвращает pandas `DataFrame` с колонками:

- `timestamp`;
- `open`;
- `high`;
- `low`;
- `close`;
- `volume`;
- `symbol`.

Он приводит `timestamp` к datetime, а OHLCV-колонки к numeric. Если период больше
1000 candles, provider делает несколько запросов: следующий `startTime` равен
`last_open_time + 1 ms`.

Для тестов реальный интернет не используется: вместо настоящего
`requests.Session` передается fake session. В production-коде можно создать
provider так:

```python
from mlcore.loaders import BinanceMarketDataProvider

provider = BinanceMarketDataProvider()
raw_df = provider.get_ohlcv("BTCUSDT", "1h", "2024-01-01", "2024-01-05")
```

Provider не сохраняет файлы и не создает `PipelineRun`. Он только получает raw
OHLCV-таблицу. Ошибки API, пустой ответ и network errors превращаются в
`BinanceMarketDataError`.

## Что делает CSV upload page

Страница `/upload/` - это первый простой UI-вход в реальный pipeline.

Она показывает форму:

- CSV file;
- symbol;
- interval;
- start_date;
- end_date;
- target_horizon;
- train_baseline;
- train_catboost.

Рядом с формой есть help-блок: required CSV columns
`timestamp`, `open`, `high`, `low`, `close`, `volume`, recommended `symbol`,
sample dataset path `data/samples/sample_ohlcv.csv` и краткое описание raw
artifact/result page flow.

После отправки формы view передает cleaned form data в `CsvPipelineUploadUseCase`.
Сам use case читает CSV через pandas, создает `PipelineRun`, сохраняет исходный
CSV в `media/datasets/raw/` и создает raw `DatasetArtifact` с `symbol` и
`row_count`. Затем он вызывает `RunPipelineUseCase`.

Так view остается тонким: он проверяет форму, вызывает один use case и решает,
сделать redirect на `/runs/<id>/` или показать ошибку формы без 500-страницы.

Если все хорошо, пользователь попадает на `/runs/<id>/`, где видны raw,
processed и final datasets, models и metrics. Если pipeline падает уже после
raw save, raw artifact остается у запуска, run получает статус `failed`, а
ошибка записывается в `error_message`.

## Что делает Binance pipeline page

Страница `/binance/` - это UI-вход в pipeline без ручного CSV-файла.

Она показывает форму:

- symbol;
- interval;
- start_date;
- end_date;
- target_horizon;
- train_baseline;
- train_catboost.

Рядом с формой есть help-блок: он объясняет, что страница скачивает Binance Spot
OHLCV candles, показывает примеры `BTCUSDT` и `1h`, описывает `target_horizon`
и перечисляет datasets/models/metrics/reports, которые появляются после запуска.

После отправки формы view передает cleaned form data в `BinancePipelineUseCase`.
Сам use case скачивает OHLCV через `BinanceMarketDataProvider`, создает
`PipelineRun`, сохраняет raw Binance dataset как parquet в `media/datasets/raw/`
и вызывает `RunPipelineUseCase`.

Если обе модели выключены, форма показывает validation error и use case не
запускается. Если ошибка случилась после создания run, пользователь попадает на
`/runs/<id>/`, где видны `failed` status и `error_message`.

Run list `/runs/` теперь содержит короткое объяснение статусов. Run detail
`/runs/<id>/` содержит notes перед секциями `DatasetArtifact`, `ModelArtifact`,
`MetricSnapshot`, `ReportArtifact` и `Stability by Period`, включая подсказку
по чтению confusion matrix.

## Что делает run_csv_pipeline command

Management command `run_csv_pipeline` - это CLI-вход в тот же сценарий, что и
страница `/upload/`.

Пример:

```powershell
.crypto\Scripts\python.exe manage.py run_csv_pipeline --csv tmp_cli_check/input.csv --symbol BTCUSDT --interval 1h --start-date 2024-01-01 --end-date 2024-01-05 --target-horizon 3
```

Команда сама не строит features и не обучает модели напрямую. Она проверяет путь
к CSV, проверяет CLI flags и вызывает `CsvPipelineUploadUseCase`. Поэтому UI и
CLI проходят через один application слой:

```text
CSV input -> CsvPipelineUploadUseCase -> RunPipelineUseCase -> FullPipelineService
```

Если указать `--skip-baseline`, baseline не обучается. Если указать
`--skip-catboost`, CatBoost не обучается. Оба flags одновременно запрещены,
потому что pipeline должен обучить хотя бы одну модель.

## Что делает run_binance_pipeline command

Management command `run_binance_pipeline` - это CLI-вход в pipeline без ручного
CSV-файла. Команда вызывает `BinancePipelineUseCase`.

Сценарий такой:

1. Создать `PipelineRun`.
2. Скачать raw OHLCV candles через `BinanceMarketDataProvider`.
3. Сохранить raw Binance dataset как parquet в `media/datasets/raw/`.
4. Создать raw `DatasetArtifact`.
5. Передать raw `DataFrame` в `RunPipelineUseCase`.

Пример:

```powershell
.crypto\Scripts\python.exe manage.py run_binance_pipeline --symbol BTCUSDT --interval 1h --start-date 2024-01-01 --end-date 2024-01-10 --target-horizon 3 --skip-catboost
```

Команда не дублирует ML-логику. Она только проверяет CLI flags и вызывает use
case:

```text
BinanceMarketDataProvider -> BinancePipelineUseCase -> RunPipelineUseCase -> FullPipelineService
```

Raw Binance artifact выбран в формате parquet, потому что это внутренний dataset,
а не пользовательский uploaded CSV.

## Что делает run_research_evaluation command

Management command `run_research_evaluation` - это offline CLI для research
checks по уже готовому final dataset.

Он принимает `.parquet` или `.csv` файл:

```powershell
.crypto\Scripts\python.exe manage.py run_research_evaluation --dataset tmp_research_check/final.parquet --output-dir tmp_research_check/out --trainer dummy --run-walk-forward --run-ablation --train-window 40 --test-window 20
```

Команда умеет запускать:

- `WalkForwardEvaluationService` и сохранять `walk_forward_<trainer>.csv`;
- `FeatureAblationService` и сохранять `ablation_<trainer>.csv`.

Доступные trainers в CLI: `dummy` и `baseline`. CatBoost пока специально не
добавлен, чтобы command оставалась быстрой для локальных research checks.

Важно: command не создает `PipelineRun`, не пишет в Django DB и не создает
`ReportArtifact`. Это просто способ воспроизводимо сохранить research таблицы в
файлы.

## Почему нельзя хранить большие datasets в SQLite

SQLite в этом проекте - это тетрадь с описанием.
А большие datasets и модели - это тяжелые коробки.

В тетрадь удобно записывать:

- run id;
- status;
- symbols;
- interval;
- путь к файлу;
- metrics;
- error message.

Но неудобно складывать туда сами большие файлы.
Если положить datasets и models прямо в SQLite, база станет тяжелой, медленной
и неудобной для backup.

Поэтому правило такое:

```text
SQLite хранит metadata.
media/ хранит большие файлы.
```

## Как данные проходят весь путь

Полная идея pipeline выглядит так:

```text
raw data
  -> clean data
  -> features
  -> target
  -> split
  -> train
  -> evaluate
  -> model artifact
```

Что означает каждый шаг:

- `raw data`: сырые свечные данные, которые когда-то будут скачиваться или
  загружаться;
- `clean data`: данные после `DataCleaner`;
- `features`: таблица после `FeatureBuilder`;
- `target`: колонка ответа после `TargetBuilder`;
- `dataset preparation`: ручной service, который сохраняет processed и final
  datasets;
- `split`: train/valid/test части после `SplitService`;
- `train`: обучение модели через trainer;
- `evaluate`: расчет metrics через `Evaluator`;
- `model artifact`: сохраненная модель через `ModelRepository`.

## Уже работает

- Metadata models в Django.
- Admin для metadata.
- Dashboard `/`.
- Binance pipeline page `/binance/`.
- CSV upload `/upload/`.
- Runs list `/runs/`.
- Run detail `/runs/<id>/`.
- Read-only Dashboard overview с ссылками на реальные pipeline entry points.
- Repositories для datasets, models и artifact paths.
- Очистка данных.
- Построение features.
- Построение target.
- Ручной `DatasetPreparationService`.
- Временной split.
- Research walk-forward folds без random shuffle.
- Research walk-forward evaluation по folds.
- Research feature ablation по группам признаков.
- Метрики качества.
- Research-анализ stability metrics по временным периодам.
- Dummy baseline trainer.
- Baseline trainer.
- CatBoost trainer.
- Ручной `DummyTrainingService`.
- Ручной `BaselineTrainingService`.
- Ручной `CatBoostTrainingService`.
- `TargetDistributionReportService`.
- `MetricsComparisonReportService`.
- `PeriodStabilityReportService`.
- `FeatureImportanceReportService`.
- `BinanceMarketDataProvider`.
- Ручной `FullPipelineService`.
- Ручной `RunPersistenceService`.
- Ручной `RunPipelineUseCase`.
- Синхронный запуск pipeline из Binance data через `/binance/`.
- Синхронный запуск pipeline из raw CSV через `/upload/`.
- CLI-запуск pipeline из raw CSV через `run_csv_pipeline`.
- CLI-запуск pipeline из Binance data через `run_binance_pipeline`.
- Offline CLI research evaluation через `run_research_evaluation`.

## Будет позже

- Async/background queue для долгих запусков.
- Более богатые dashboard previews для research outputs.
