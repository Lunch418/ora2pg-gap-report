# Changelog

Формат по мотивам [Keep a Changelog](https://keepachangelog.com/ru/1.0.0/).
Проект следует [SemVer](https://semver.org/lang/ru/) в упрощённом виде,
пока не достигнет 1.0.0: minor-версия — новые детекторы/возможности,
patch — исправления в существующих.

## [Unreleased]

## [0.4.0] - 2026-08-16

### Added
- 7 новых детекторов, GAP-022…GAP-028. Реестр — теперь 28 подтверждённых
  gap'ов, см. `docs/research/GAP_REGISTRY.md`:
  - `cross_apply` — `CROSS APPLY`/`OUTER APPLY`, синтаксиса `APPLY` нет в
    PostgreSQL вообще.
  - `oracle_text` — домен-индекс `INDEXTYPE IS CTXSYS.*` (Oracle Text)
    отбрасывается целиком; вызовы `CONTAINS`/`CATSEARCH`/`MATCHES` не
    переносятся.
  - `recursive_with` — нативная рекурсивная `WITH ... AS (...)` (не через
    `CONNECT BY`) без обязательного в PostgreSQL ключевого слова
    `RECURSIVE`.
  - `invisible_index` — индекс `INVISIBLE` теряет своё скрытие от
    оптимизатора.
  - `read_only_table` — `CREATE TABLE ... READ ONLY` теряет гарантию
    неизменяемости; `INSERT` проходит там, где Oracle гарантированно
    блокирует его (`ORA-12081`).
  - `materialized_view_log` — `CREATE MATERIALIZED VIEW LOG` не
    конвертируется вообще, след только в DEBUG-логе.
  - `identity_column` — `GENERATED ... AS IDENTITY (...)` с опциями:
    настоящий баг двойных скобок в самой подстановке ora2pg (не пропуск
    конвертации, а поломанная конвертация — код падает при загрузке DDL).
- `docs/research/AUDIT.md` и `scripts/audit_gap_test_counts.py` обновлены
  под все 28 gap'ов.

### Fixed
- Системный баг статeмент-скоупинга: `DBMS_METADATA.GET_DDL` (этот же
  проект использует его для выгрузки DDL из Oracle) по умолчанию не
  ставит `;` в конце оператора, а часть детекторов ограничивала «свой»
  оператор как «до следующей `;`, а если её нет — до конца файла», из-за
  чего конструкция из более поздней таблицы могла ошибочно приписаться
  более ранней, незавершённой. Затронуло в том числе уже опубликованные
  `table_partitioning` и `external_table`, не только новые детекторы этого
  релиза. Добавлен общий хелпер `statement_end()` в `plsql_lex.py`,
  применён в 8 детекторах: `table_partitioning`, `external_table`,
  `invisible_column`, `global_temp_table`, `oracle_text`,
  `invisible_index`, `read_only_table`, `identity_column`.
- `invisible_index`/`read_only_table`: ложные срабатывания на столбце с
  тем же именем, что и модификатор (`invisible`/`read_only` как
  идентификатор столбца, в том числе в двойных кавычках) — теперь
  исключены.
- `invisible_index`/`read_only_table`/`oracle_text`: номер строки в
  находке теперь указывает на сам модификатор/секцию (`INVISIBLE`/`READ
  ONLY`/`INDEXTYPE IS ...`), а не на строку с открывающим `CREATE
  TABLE`/`CREATE INDEX` — важно для многострочного DDL.
- `materialized_view_log`: severity поднята с `medium` на `high` — тот же
  профиль риска, что у `table_partitioning`/`external_table` (конструкция
  молча пропадает без ошибки PostgreSQL, но означает реальную
  архитектурную потерю).

## [0.3.0] - 2026-08-15

### Added
- 14 новых детекторов, GAP-008…GAP-021: `pivot_clause`, `object_type`,
  `with_function`, `flashback_query`, `global_temp_table`,
  `table_partitioning`, `connect_by_nocycle`, `context_object`,
  `insert_all`, `json_table`, `external_table`, `sql_macro`,
  `invisible_column`, `collection_type`. Реестр — теперь 21 подтверждённый
  gap, см. `docs/research/GAP_REGISTRY.md`.
- Флаг `--version`.
- Поддержка директорий в качестве аргумента — рекурсивный поиск
  `.sql`/`.pks`/`.pkb` файлов, не только явный список файлов.
- `docs/research/AUDIT.md` — сводная проверка доказательной базы по
  каждому из 21 gap'а (research-документ, реальный вывод ora2pg,
  expected/actual, тесты, включая guard-тесты на ложные срабатывания) и
  `scripts/audit_gap_test_counts.py`, который эти числа пересчитывает.
- `ruff` — job линтинга в CI (с явно закреплённым набором правил, не
  implicit-default — см. `[tool.ruff.lint]` в `pyproject.toml`).

### Fixed
- Атрибуция находок (`object_name` в отчёте) для реального кода, а не
  только синтетических примеров — найдено прогоном инструмента на двух
  больших открытых PL/SQL-кодовых базах (`mortenbra/alexandria-plsql-utils`,
  `oracle-samples/db-sample-schemas`, суммарно ~143k строк):
  - `PACKAGE`-спецификация (без `BODY`) и `CREATE VIEW`/`CREATE MATERIALIZED
    VIEW` теперь распознаются как контейнеры для атрибуции — раньше
    находки внутри них уходили в `UNKNOWN`.
  - `CREATE`-конструкция внутри списка привилегий `GRANT`/`REVOKE`
    (`GRANT ..., CREATE VIEW TO oe;`) больше не принимается за настоящее
    объявление объекта.
  - Строчные комментарии SQL*Plus (`REM`/`REMARK`) теперь маскируются —
    раньше реальное объявление, которому предшествовали только такие
    комментарии, могло потерять атрибуцию.
- `table_partitioning`: секционированный индекс (`CREATE INDEX ...
  GLOBAL PARTITION BY RANGE ...`) больше не приписывается случайной
  несвязанной таблице; добавлена поддержка стратегий `REFERENCE`/`SYSTEM`.
- `insert_all`: окно поиска `INTO` после `INSERT ALL`/`FIRST` расширено —
  не пропускало находку при длинном условии `WHEN`.
- `invisible_column`: `INVISIBLE UNIQUE`/`INVISIBLE PRIMARY KEY` и другие
  inline-ограничения после модификатора теперь тоже флагуются.
- `bulk_collect`: схемный `CREATE TYPE ... EDITIONABLE ... IS TABLE OF`
  больше не дублируется как находка этого детектора.
- Директории: файл, доступный одновременно напрямую и через директорию
  (`schema/ schema/logger.pkb`), больше не учитывается дважды; расширения
  файлов (`.SQL`/`.PKB`) сопоставляются без учёта регистра.

## [0.2.0] - 2026-08-14

### Added
- GAP-002 `merge_delete_clause` — `MERGE ... DELETE WHERE`.
- GAP-003 `bulk_collect` — `TYPE ... IS TABLE OF` / `BULK COLLECT INTO` /
  `FORALL`.
- GAP-006 `database_link` — `table@dblink_name`.
- GAP-007 `model_clause` — `MODEL PARTITION BY ... MEASURES ... RULES`.
- Полностью переработанный терминальный вывод (`rich`): баннер,
  сводная панель, дерево «объекты с наибольшим числом находок»,
  секция рекомендаций по каждому сработавшему детектору, панель оценки
  трудозатрат (лучший/среднее/худший случай).
- Флаги `--severity` и `--object` для фильтрации находок в отчёте.
- `docs/research/GAP_REGISTRY.md` — формализованный реестр gap'ов с
  версией ora2pg, на которой каждый подтверждён, и статусом
  (`confirmed`/`fixed-upstream`/`wont-fix`).
- PyPI-бейдж в README.

## [0.1.0] - 2026-08-14

Первый релиз.

### Added
- GAP-001 `autonomous_tx` — `PRAGMA AUTONOMOUS_TRANSACTION`, недооценка
  стоимости в `SHOW_REPORT`/`--estimate_cost`.
- GAP-004 `compound_triggers` — `COMPOUND TRIGGER`, тихий провал
  файлового парсера ora2pg.
- GAP-005 `connect_by` — баг подстановки `LEVEL` в сгенерированном
  `WITH RECURSIVE` (опционально, `--check-connect-by`, требует ora2pg).
- `dbms_utl_calls` — классификатор конкретных вызовов `DBMS_*`/`UTL_*`.
- CLI: `--format` (terminal/markdown/json), `--output`.
- Выгрузка DDL напрямую из Oracle: `ora2pg-gap-export`.
