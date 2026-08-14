# ora2pg-gap-report

[![tests](https://github.com/Lunch418/ora2pg-gap-report/actions/workflows/tests.yml/badge.svg)](https://github.com/Lunch418/ora2pg-gap-report/actions/workflows/tests.yml)

Инструмент для оценки миграции Oracle → PostgreSQL Pro (Standard/Certified) **до** её начала.

## Проблема

При миграции с Oracle на Postgres Pro в сегменте Standard/Certified (то есть без
лицензии на Postgres Pro Enterprise и без проприетарной утилиты `ora2pgpro`)
единственный доступный автоматический конвертер — открытый
[`ora2pg`](https://github.com/darold/ora2pg). По независимым оценкам он закрывает
в среднем ~80% задачи перевода PL/SQL → PL/pgSQL. Оставшиеся ~20% (пакеты,
автономные транзакции, `CONNECT BY`, вызовы `DBMS_*`/`UTL_*`, составные триггеры)
сейчас разбираются вручную и, как правило, обнаруживаются постфактум — когда
что-то уже сломалось в проде.

## Что делает этот инструмент

Сканирует схему Oracle **до** миграции и говорит: какие конкретно объекты
`ora2pg` пропустит без предупреждения, недооценит по трудоёмкости или
сконвертирует потенциально некорректно — и почему. Не замена `ora2pg` —
надстройка над ним, спроектированная по результатам эмпирической проверки
(`docs/research/step0-show-report-baseline.md`), а не по одним лишь
предположениям.

## Статус

Шаг 0 (валидация предпосылки — сверка `ora2pg SHOW_REPORT` с заявленным
списком проблемных конструкций) завершён, см.
`docs/research/step0-show-report-baseline.md`. Ключевой вывод: сам факт
`CREATE PACKAGE` ora2pg переносит корректно — детектор для него не нужен.

Инструмент работает end-to-end: все четыре запланированных детектора
реализованы (Задача 1), обёртка над `ora2pg` есть (Задача 2), эвристика
трудозатрат есть (Задача 3), плюс живая выгрузка DDL прямо из Oracle-схемы
— то есть весь MVP из брифа закрыт. Всё покрыто тестами на реальном
открытом PL/SQL-коде (включая живые прогоны настоящего `ora2pg`, не
только чтение исходников), ставится через `pip install` и сразу даёт
консольные команды.

Не сделана только Задача 4 (частичная автоматизация переноса простых
пакетов) — по брифу это осознанный бэклог, не MVP.

| Детектор | Статус | Что ловит |
|---|---|---|
| `autonomous_tx` | готово | `PRAGMA AUTONOMOUS_TRANSACTION` внутри `PACKAGE BODY` — ora2pg конвертирует через dblink, но занижает/теряет стоимость в `SHOW_REPORT`/`--estimate_cost` |
| `compound_triggers` | готово | `COMPOUND TRIGGER` — файловый парсер ora2pg тихо возвращает 0 триггеров, без единой ошибки |
| `dbms_utl_calls` | готово | Классификатор конкретных вызовов `DBMS_*`/`UTL_*` — что из них ora2pg реально конвертирует, а что остаётся как есть |
| `connect_by` | готово (опционально, `--check-connect-by`) | Линтинг сгенерированного ora2pg `WITH RECURSIVE` на баг с `LEVEL` — единственный детектор, которому нужен установленный `ora2pg` |
| `ora2pg_wrapper.py` | готово (Задача 2) | Запуск `ora2pg` по типам объектов на выгруженном DDL, парсинг `--estimate_cost` |
| `oracle_connector.py` / `oracle_export.py` | готово | Живая выгрузка `PACKAGE BODY`/`TRIGGER` DDL прямо из Oracle-схемы через `DBMS_METADATA.GET_DDL` (thin-режим `python-oracledb`, без Oracle Instant Client) |

## Установка и использование

```sh
pip install ora2pg-gap-report   # (или: pip install . из клона репозитория)
```

Сама детекторная библиотека (`detectors/`, `models.py`,
`report_generator.py`) — чистый Python без единой внешней зависимости, её
можно импортировать отдельно (например, в своих скриптах) вообще без
установки чего-либо ещё. У CLI есть одна обязательная зависимость —
[`rich`](https://github.com/Textualize/rich), только ради приятного
терминального вывода; ставится сама через `pip install`.

Сразу после установки доступна команда:

```sh
ora2pg-gap-report path/to/schema_dump.pkb another_file.sql
```

В интерактивном терминале по умолчанию — цветной отчёт: сводная панель
(сколько найдено, разбивка по severity, грубая оценка часов), компактная
таблица находок и пояснения под каждый сработавший детектор. Для
скриптов/redirect — `--format markdown` или `--format json` (тоже
работают как формат по умолчанию, если stdout не терминал):

```sh
ora2pg-gap-report path/to/schema_dump.pkb --format json --output report.json
ora2pg-gap-report path/to/schema_dump.pkb --format markdown > report.md

# Опционально: линтинг сгенерированного ora2pg кода для CONNECT BY.
# Требует установленный ora2pg (см. https://github.com/darold/ora2pg) — 
# единственная внешняя (не-Python) зависимость во всём проекте, и только
# для этой конкретной проверки.
ora2pg-gap-report path/to/schema_dump.pkb --check-connect-by
```

Файлы с DDL можно передавать как есть — один файл может содержать сразу
несколько пакетов/триггеров, детекторы разбирают границы объектов сами.

Для разработки/тестов из клона репозитория:

```sh
pip install -e ".[dev]"   # editable-режим + pytest
pytest
```

### Выгрузка DDL прямо из Oracle (опционально)

Если под рукой живая Oracle-схема, а не уже готовый DDL-дамп:

```sh
pip install "ora2pg-gap-report[oracle]"   # добавляет python-oracledb, thin-режим, без Instant Client

ora2pg-gap-export --dsn host:1521/ORCLPDB1 --user hr --output-dir dumps/
# пароль — из переменной окружения ORACLE_PASSWORD, либо будет запрошен интерактивно

ora2pg-gap-report dumps/*.sql
```

`ora2pg-gap-export` — отдельная команда, не флаг у `ora2pg-gap-report`,
специально: выгрузка требует сетевого доступа к Oracle, анализ — никогда.
В закрытом контуре это часто две разные машины (jump host с доступом к БД
и изолированная рабочая станция для анализа) — единственное, что должно
пересечь границу между ними, это уже выгруженные `.sql` файлы.

Пример реального вывода на открытом пакете —
`docs/examples/logger-autonomous_tx-report.md`.

Оценка трудозатрат в отчёте — грубая эвристика по severity (диапазон
часов, не точечное число), явно помеченная как неоткалиброванная. Не
выдавать клиенту как обещание без калибровки на реальных миграциях (см.
"Честное ограничение" в PROJECT_BRIEF.md).

### Установка без интернета (закрытый контур)

Целевая аудитория этого инструмента — как раз изолированные сети без
выхода наружу, поэтому `pip install` там обычно не вариант. Решение —
собрать самодостаточный архив на машине С интернетом, перенести его
любым доступным способом (`scp`/`sftp`/через jump host/на флешке) и
поставить на целевой машине уже совсем без сети:

```sh
# На машине с интернетом, из клона репозитория:
python scripts/build_offline_bundle.py --oracle   # --oracle опционально, --dev для pytest
# → ora2pg-gap-report-offline.tar.gz (пакет + rich + всё транзитивно,
#   включая oracledb и его зависимости, если указан --oracle)

scp ora2pg-gap-report-offline.tar.gz user@jump-host:/tmp/
# ...дальше как получится добраться до целевой машины в контуре —
# sftp, ещё один jump host, физический перенос

# На целевой машине БЕЗ интернета:
tar xzf ora2pg-gap-report-offline.tar.gz
cd ora2pg-gap-report-offline
./install.sh oracle        # или: python3 install.py oracle
```

`install.sh`/`install.py` вызывают `pip install --no-index --find-links=./wheels
...` — pip ставит целиком из положенных рядом `.whl`-файлов, ни одного
обращения в сеть. Проверено реальным прогоном: собранный архив
установлен в чистый venv через `--no-index`, консольные команды и
`import oracledb` отработали, реальный анализ дал корректный результат
— без единого сетевого запроса.

`rich` и его зависимости (`markdown-it-py`, `pygments`, `mdurl`) —
чистый Python, один набор wheel-файлов работает везде. `oracledb`
(только при `--oracle`) собирает платформозависимые wheel — если
машина сборки отличается от целевой по ОС/архитектуре/версии Python,
передайте `--platform`/`--python-version`/`--abi` в
`build_offline_bundle.py` (см. `--help`), чтобы скачать wheel именно
под целевую платформу, а не под ту, где запущен скрипт.

## Архитектура

`ora2pg SHOW_REPORT` целиком не имеет офлайн-режима — он требует живого
подключения к Oracle (`ORACLE_DSN`). Офлайн от DDL-дампа работает только
анализ *отдельных типов объектов* (`-t PACKAGE`, `-t TRIGGER`, `-t FUNCTION`,
…) — именно так работает `ora2pg_wrapper.py`, а не через `SHOW_REPORT`. Это
принципиально для целевой аудитории — закрытые контуры, air-gapped среды,
госсектор.

Три из четырёх детекторов (`autonomous_tx`, `compound_triggers`,
`dbms_utl_calls`) анализируют Oracle-исходник напрямую и не требуют
установленного `ora2pg` — чистый Python, без внешних зависимостей.
Четвёртый (`connect_by`) устроен иначе: он линтит *сгенерированный*
ora2pg-код, а не исходник (ora2pg сам неплохо считает CONNECT BY —
ценность не в обнаружении, а в проверке качества конвертации), поэтому
ему нужен реальный `ora2pg` и он подключается только через
`--check-connect-by`.

```
pyproject.toml                 # единственный источник правды по зависимостям/точкам входа
ora2pg_gap_report/
├── models.py                 # Finding — общая структура находки для всех детекторов
├── plsql_lex.py               # общая инфраструктура: маскирование строк/комментариев
│                               # (включая q-quote), сопоставление блоков BEGIN/CASE/IF/LOOP...END,
│                               # разбор идентификаторов — используется всеми детекторами
├── oracle_connector.py         # готово: живая выгрузка PACKAGE BODY/TRIGGER через DBMS_METADATA.GET_DDL
├── oracle_export.py            # готово: консольная команда ora2pg-gap-export
├── detectors/
│   ├── autonomous_tx.py       # готово: PRAGMA AUTONOMOUS_TRANSACTION в PACKAGE BODY
│   ├── compound_triggers.py   # готово: COMPOUND TRIGGER — тихий провал парсинга у ora2pg
│   ├── dbms_utl_calls.py      # готово: классификатор конкретных DBMS_*/UTL_* функций
│   └── connect_by.py          # готово: линтинг сгенерированного WITH RECURSIVE (нужен ora2pg)
├── ora2pg_wrapper.py           # готово: запуск ora2pg по типам объектов, парсинг --estimate_cost
├── cli.py                     # готово: консольная команда ora2pg-gap-report
├── effort_estimator.py         # готово: грубая эвристика по severity, диапазон часов
├── report_generator.py         # готово: JSON + Markdown (машиночитаемые форматы)
└── terminal_report.py          # готово: цветной вывод через rich (единственная зависимость
                                #          библиотеки-детекторов не касается, только CLI)
tests/
├── fixtures/                  # реальные захваченные прогоны ora2pg — тесты парсера не требуют
│                               # установленного ora2pg, кроме нескольких live-тестов
│                               # (пропускаются автоматически, если ora2pg не найден в PATH)
docs/research/                 # step 0: валидация предпосылок, реальные PL/SQL примеры
docs/examples/                 # примеры вывода детекторов на реальных данных
scripts/
├── build_offline_bundle.py     # сборка автономного архива для установки без интернета
├── oracle-test-compose.yml     # Oracle Free 23ai в Docker для живой проверки
├── setup_oracle_test_schema.sql
└── verify_against_live_oracle.py
.github/workflows/tests.yml     # CI: pytest на 3.10-3.13 + сборка и smoke-test пакета
```

### Проверка на живой Oracle (Docker)

Юнит-тесты `oracle_connector.py` идут на fake-соединении
(`tests/fakes/fake_oracle.py`) — быстро, детерминированно, не требует
Oracle. Но живой путь ("подключился к настоящей Oracle → выгрузил через
`DBMS_METADATA.GET_DDL` → проанализировал") ими не покрыт. Для этого:

```sh
docker compose -f scripts/oracle-test-compose.yml up -d
docker compose -f scripts/oracle-test-compose.yml logs -f   # ждать "DATABASE IS READY TO USE"

pip install -e ".[oracle]"
ORACLE_DSN=localhost:1521/FREEPDB1 ORACLE_USER=testuser ORACLE_PASSWORD=testpass1 \
  python scripts/verify_against_live_oracle.py
```

Скрипт создаёт пару служебных таблиц (`scripts/setup_oracle_test_schema.sql`
— триггерам, в отличие от пакетов, нужна реально существующая целевая
таблица), заливает реальные фикстуры из `docs/research/samples/` как
есть, выгружает их обратно живым `DBMS_METADATA.GET_DDL`, прогоняет
детекторы и сверяет счётчики с уже независимо проверенными на этих же
файлах как на тексте (`tests/`). Если в `PATH` есть `ora2pg` — заодно
пробует `SHOW_REPORT` против живого подключения, впервые проверяя вживую
(а не только по чтению исходников) те места
`docs/research/step0-show-report-baseline.md`, что были помечены "по
коду, не подтверждено".

`gvenzl/oracle-free:23-slim` — контейнерный пакет официального
бесплатного дистрибутива Oracle (не подделка, тот же движок), просто с
более удобной для CI/тестов оберткой, чем прямой образ Oracle Container
Registry.

**Статус:** прогнано вживую (2026-08-14) на `gvenzl/oracle-free:23-slim`
— `autonomous_tx`, `dbms_utl_calls` и `compound_triggers` совпали с
ожидаемыми счётчиками (8/68/2) на DDL, реально выгруженном через
`DBMS_METADATA.GET_DDL` из настоящей Oracle. Песочница, где вёлся
остальной проект, блокирует Docker Hub и `container-registry.oracle.com`
на уровне сетевой политики, так что этот прогон был сделан не мной, а
пользователем на своей машине — `ora2pg` в `PATH` при этом не было,
поэтому кусок с реальным `SHOW_REPORT` пока не проверен (только
`split_sql_statements` и остальной пайплайн без него).

## Как проверялась корректность

Каждый компонент (детекторы, `plsql_lex.py`, `ora2pg_wrapper.py`,
`oracle_connector.py`) прошёл цикл ветка → тесты на реальном открытом
PL/SQL-коде (и, где применимо, на живом прогоне настоящего `ora2pg`) →
независимый ревью через `code-review`-субагента → фикс найденного →
повторный прогон тестов → только потом мерж в `main`. Найдено и
исправлено 22 реальных бага за время разработки (детали — в истории
коммитов `git log --oneline`): неверная граница вложенных подпрограмм,
маскирование строк/комментариев без учёта строковых литералов (включая
Oracle q-quote синтаксис), неверная привязка имени пакета при нескольких
пакетах в одном файле, `$`/`#` в идентификаторах, отсутствие
пересортировки при мульти-файловом сканировании, жёстко зашитый тип
объекта для ora2pg, непойманные варианты формата вывода ora2pg для разных
`-t` режимов, path traversal через имена объектов Oracle в
`oracle_connector.py`, запись DDL без явной кодировки UTF-8 и другое. Это
не разовая проверка — тот же цикл стоит повторять для каждого следующего
изменения.

## Лицензия

MIT, см. [LICENSE](LICENSE).
