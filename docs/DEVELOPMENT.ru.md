*[English](DEVELOPMENT.md) | Русский*

# Разработка

Как проверять изменения, что за корпус реального кода используется, как
подтвердить новый детектор на живой Oracle. Для "что это и зачем" — см.
[README.md](../README.ru.md); для внутренней архитектуры — см.
[ARCHITECTURE.md](ARCHITECTURE.ru.md).

## Как добавляется новый детектор

Этот проект не пытается найти детектор под каждую специфичную для Oracle
конструкцию. `ROWNUM`, `DECODE`, `NVL`, `SYSDATE`, `%TYPE`, sequences,
стандартная семантика исключений — всё это `ora2pg` конвертирует корректно,
и детекторы под них не нужны, как бы по-ораклиному сложно они ни звучали.

Новый детектор появляется только после того, как гипотеза проверена на
практике:

1. Берётся конкретная Oracle-конструкция.
2. Собирается минимальный воспроизводимый пример.
3. Пример прогоняется через настоящий `ora2pg`.
4. Сгенерированный PostgreSQL-код проверяется на корректность.
5. Если `ora2pg` справился — гипотеза отклоняется, детектора не будет.
   Если нашёлся реальный, воспроизводимый баг — заводится тест-фикстура и
   пишется детектор.

Так, например, отсеялась изначальная гипотеза про `CREATE PACKAGE` — на
первый взгляд очевидный кандидат, а на практике `ora2pg` переносит его без
проблем (`docs/research/step0-show-report-baseline.md`). И так же
подтвердились `COMPOUND TRIGGER` и баг с `LEVEL` в `CONNECT BY` — оба
воспроизведены на реальном прогоне `ora2pg`, а не предположены по описанию.

Все подтверждённые находки пронумерованы и собраны в
[`research/GAP_REGISTRY.md`](research/GAP_REGISTRY.md) — по каждой
указано, каким детектором она покрыта и на какой версии `ora2pg`
подтверждена. [`research/AUDIT.md`](research/AUDIT.md) — сводная
проверка доказательной базы по каждому подтверждённому gap'у
(research-документ, реальный вывод ora2pg, expected/actual, тесты,
включая guard-тесты на ложные срабатывания).

## Регистрация целостности (doctor)

Реестр (`ora2pg_gap_report/gap_registry.py`) и файловая структура
проверяются автоматически:

```sh
python3 scripts/doctor.py     # у каждого GAP-NNN есть research-документ, детектор и тесты
python3 scripts/audit_gap_test_counts.py   # пересчитать колонку "Тесты" в AUDIT.md
```

`doctor.py` — часть CI (job `lint`): если реестр разъехался с файлами на
диске (например, кто-то добавил gap в `gap_registry.py`, но забыл
детектор или тест), сборка падает сразу, а не остаётся незамеченной до
следующего ручного аудита. Отдельная проверка — что файловое дерево
детекторов в `ARCHITECTURE.md` не разошлось со списком файлов в
`ora2pg_gap_report/detectors/` (ровно тот класс проблемы, из-за которого
README какое-то время содержало устаревшее описание архитектуры) —
тоже часть `doctor.py`, а не только про registry.

## Тестирование

```sh
pip install -e ".[dev]"   # editable-режим + pytest/ruff/mypy
pytest
ruff check ora2pg_gap_report/ tests/
mypy                       # ora2pg_gap_report/ + scripts/, конфиг в pyproject.toml
```

`mypy` настроен с `disallow_untyped_defs` — не просто "не падает на
аннотированном коде", а реально требует аннотаций у каждой функции.
`oracledb` (опциональная зависимость extra `oracle`) размечен как
`ignore_missing_imports` — типы из него используются только под `if
TYPE_CHECKING:` (`oracle_connector.py`), поэтому пакет остаётся
импортируемым без него, и `mypy` не падает в CI, где `oracledb` не
установлен.

Детекторы и лексер проверены на реальном открытом PL/SQL-коде — не
только на синтетических примерах. Помимо точечных фикстур (Logger,
составной триггер из Apress), детекторы прогонялись целиком на
247 298 строках (точный свежий подсчёт по `git clone --depth 1` каждого
репозитория) из семи независимых открытых проектов: официальных
демо-схем Oracle (`oracle-samples/db-sample-schemas`), библиотеки утилит
`mortenbra/alexandria-plsql-utils`, фреймворка юнит-тестирования
`utPLSQL/utPLSQL`, логгера `OraOpenSource/Logger`, лексера/токенизатора
`method5/plsql_lexer`, генератора Excel-файлов `mbleron/ExcelGen` и
шаблонизатора `osalvador/tePLSQL` — ноль падений, только одна честно
задокументированная граница применимости (см.
`test_real_open_source_logger_install_script_
anonymous_block_is_unknown_not_a_crash` в `tests/test_bulk_collect.py`).
Подробности и полный список corpus-validated детекторов — в
`research/AUDIT.md`.

### Проверка на живой Oracle

Юнит-тесты `oracle_connector.py` идут на fake-соединении
(`tests/fakes/fake_oracle.py`) — быстро, детерминированно, не требует
Oracle. Живой путь ("подключился к настоящей Oracle → выгрузил через
`DBMS_METADATA.GET_DDL` → проанализировал") ими не покрыт — для него
нужна настоящая база:

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
прогоняет `SHOW_REPORT` против живого подключения.

`gvenzl/oracle-free:23-slim` — контейнерный пакет официального
бесплатного дистрибутива Oracle (тот же движок), просто с более удобной
для CI/тестов оберткой, чем прямой образ Oracle Container Registry.
