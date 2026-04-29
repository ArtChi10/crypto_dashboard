# Beginner code explanation

Этот документ объясняет код проекта `crypto_dashboard` простыми словами.
Представьте, что проект - это журнал лабораторных опытов по ML: мы записываем,
какой опыт хотели запустить, какие данные использовали, какую модель обучили и
какие результаты получили.

## Что такое Django в этом проекте

Django - это каркас веб-приложения.

В этом проекте Django отвечает за:

- страницы в браузере;
- форму создания запуска;
- admin-панель;
- SQLite database;
- models, то есть таблицы metadata.

Django здесь не обучает модель сам. Он дает удобную оболочку: где посмотреть
запуски, где создать запись запуска и где хранить metadata.

## Зачем нужны apps dashboard и runs

В Django проект обычно делят на apps. App - это отдельная часть проекта со
своей задачей.

`dashboard` отвечает за главную страницу `/`.

На ней есть:

- краткий статус;
- форма создания нового `PipelineRun`;
- список последних запусков.

`runs` отвечает за страницы запусков:

- `/runs/` - список всех запусков;
- `/runs/<id>/` - детали одного запуска.

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

Сейчас создание `PipelineRun` через UI не запускает полный pipeline. Оно только
создает metadata-запись со статусом `Created`.

## Что такое ArtifactRepository

`ArtifactRepository` строит правильные пути для файлов.

Например, если нужно сохранить raw dataset для run `12`, repository сделает
понятный путь вроде:

```text
media/datasets/raw/raw_run_12_BTCUSDT_20260427_120501.parquet
```

Он следит, чтобы:

- dataset artifacts попадали в `datasets/raw`, `datasets/processed` или
  `datasets/final`;
- model artifacts попадали в `models`;
- report artifacts попадали в `reports`;
- имена файлов были предсказуемыми.

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

## Что такое BaselineTrainer

`BaselineTrainer` обучает простую базовую модель.

Сейчас это pipeline из:

- `StandardScaler`;
- `LogisticRegression`.

Baseline нужен как первая точка сравнения. Если потом появится сложная модель,
например CatBoost service, ее можно будет сравнить с baseline.

`BaselineTrainer` берет только numeric feature columns и не использует:

- `target`;
- `timestamp`;
- `symbol`.

## Что такое CatBoostTrainer

`CatBoostTrainer` обучает `CatBoostClassifier`.

Он уже реализован как trainer: его можно вызвать из Python-кода и передать ему
train/valid данные.

Важно: `CatBoostTrainer` - это низкоуровневый trainer. Он умеет обучить модель,
но сам не делает split, не считает metrics и не сохраняет artifact.

Для полного ручного сценария из Python теперь есть `CatBoostTrainingService`.
UI пока не запускает CatBoost training автоматически.

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

Но сейчас он не подключен к Dashboard. UI не вызывает его автоматически.

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

Но сейчас он не подключен к Dashboard. UI не вызывает его автоматически.

## Что делает FullPipelineService

`FullPipelineService` - это верхний ручной service для in-memory запуска
текущего ML-пайплайна.

Он получает raw OHLCV `DataFrame` и делает так:

1. Запускает `DatasetPreparationService`.
2. Загружает final parquet dataset через `DatasetRepository`.
3. Если включен `train_baseline`, запускает `BaselineTrainingService`.
4. Если включен `train_catboost`, запускает `CatBoostTrainingService`.
5. Возвращает общий результат: preparation result, baseline result и CatBoost
   result.

Если обе training-галочки выключены, service сразу выдаст `ValueError`.

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
- `ModelArtifact` для baseline, если baseline запускался;
- `MetricSnapshot` для baseline, если baseline запускался;
- `ModelArtifact` для CatBoost, если CatBoost запускался;
- `MetricSnapshot` для CatBoost, если CatBoost запускался.

Он не обучает модели, не строит признаки, не скачивает данные и не меняет UI.
Он только записывает в SQLite ссылки на уже созданные файлы и уже посчитанные
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

Важно: use case не скачивает данные из Binance и не подключен к UI. Raw
`DataFrame` ему должен передать внешний код.

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
- Runs list `/runs/`.
- Run detail `/runs/<id>/`.
- Создание `PipelineRun` через UI.
- Repositories для datasets, models и artifact paths.
- Очистка данных.
- Построение features.
- Построение target.
- Ручной `DatasetPreparationService`.
- Временной split.
- Метрики качества.
- Baseline trainer.
- CatBoost trainer.
- Ручной `BaselineTrainingService`.
- Ручной `CatBoostTrainingService`.
- Ручной `FullPipelineService`.
- Ручной `RunPersistenceService`.
- Ручной `RunPipelineUseCase`.

## Будет позже

- Binance loader.
- Full pipeline button в UI.
- Полный pipeline через UI.
- Автоматическая запись реальных metrics в UI.
- Автоматическое создание model artifacts через UI.
