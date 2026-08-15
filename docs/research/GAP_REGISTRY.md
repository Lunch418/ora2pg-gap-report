# Реестр подтверждённых gap'ов

Каждая строка — конкретная Oracle-конструкция, для которой эмпирически
подтверждено (не предположено), что `ora2pg` конвертирует её некорректно
или пропускает без предупреждения. См. «Методология» в основном
[README](../../README.md) — детектор появляется только после того, как
гипотеза прошла этот цикл; отклонённые гипотезы в реестр не попадают —
они задокументированы отдельно, в `step0-show-report-baseline.md`
(разделы 1 и частично 4) и `rejected-hypotheses.md`.

Номера присвоены в порядке документирования, не в порядке значимости или
хронологии реализации — GAP-002/003 были задокументированы раньше
GAP-001/004/005 просто потому, что реестр появился позже них.

| ID | Конструкция | Детектор | Статус | Подтверждено на ora2pg | Документ |
|---|---|---|---|---|---|
| GAP-001 | `PRAGMA AUTONOMOUS_TRANSACTION` — недооценка стоимости в package body | `autonomous_tx` | confirmed | 25.0 | [gap-001](gap-001-autonomous-transaction.md) |
| GAP-002 | `MERGE ... WHEN MATCHED THEN UPDATE SET ... DELETE WHERE ...` | `merge_delete_clause` | confirmed | 25.0 | [gap-002](gap-002-merge-delete-clause.md) |
| GAP-003 | `TYPE ... IS TABLE OF` / `BULK COLLECT INTO` / `FORALL` | `bulk_collect` | confirmed | 25.0 | [gap-003](gap-003-bulk-collect-forall.md) |
| GAP-004 | `COMPOUND TRIGGER` — тихий провал файлового парсера | `compound_triggers` | confirmed | 25.0 | [gap-004](gap-004-compound-trigger.md) |
| GAP-005 | `CONNECT BY` — баг подстановки `LEVEL` в `WITH RECURSIVE` | `connect_by` | confirmed | 25.0 | [gap-005](gap-005-connect-by-level.md) |
| GAP-006 | `table@dblink_name` — прямая ссылка на удалённую БД | `database_link` | confirmed | 25.0 | [gap-006](gap-006-database-link.md) |
| GAP-007 | `MODEL PARTITION BY ... DIMENSION BY ... MEASURES ... RULES` | `model_clause` | confirmed | 25.0 | [gap-007](gap-007-model-clause.md) |
| GAP-008 | `PIVOT`/`UNPIVOT` | `pivot_clause` | confirmed | 25.0 | [gap-008](gap-008-pivot-unpivot.md) |
| GAP-009 | `CREATE TYPE ... AS OBJECT` / `TYPE BODY` — вне оценки трудозатрат вообще | `object_type` | confirmed | 25.0 | [gap-009](gap-009-object-type.md) |
| GAP-010 | `WITH FUNCTION`/`WITH PROCEDURE` — парсер разваливает структуру исходника | `with_function` | confirmed | 25.0 | [gap-010](gap-010-with-function.md) |
| GAP-011 | `AS OF TIMESTAMP`/`AS OF SCN` — flashback-запрос | `flashback_query` | confirmed | 25.0 | [gap-011](gap-011-flashback-query.md) |
| GAP-012 | `CREATE GLOBAL TEMPORARY TABLE` — теряется секция `ON COMMIT` | `global_temp_table` | confirmed | 25.0 | [gap-012](gap-012-global-temp-table.md) |
| GAP-013 | `PARTITION BY RANGE/LIST/HASH` — секционирование таблицы отбрасывается целиком | `table_partitioning` | confirmed | 25.0 | [gap-013](gap-013-table-partitioning.md) |
| GAP-014 | `CONNECT BY NOCYCLE` / `ORDER SIBLINGS BY` — структурное разрушение блока | `connect_by_nocycle` | confirmed | 25.0 | [gap-014](gap-014-connect-by-nocycle.md) |
| GAP-015 | `CREATE CONTEXT` — application context не конвертируется вообще | `context_object` | confirmed | 25.0 | [gap-015](gap-015-context.md) |
| GAP-016 | `INSERT ALL`/`INSERT FIRST` — многотабличная вставка | `insert_all` | confirmed | 25.0 | [gap-016](gap-016-insert-all.md) |
| GAP-017 | `JSON_TABLE(...)` — не существует в PostgreSQL 16 и старше | `json_table` | confirmed | 25.0 | [gap-017](gap-017-json-table.md) |
| GAP-018 | `CREATE TABLE ... ORGANIZATION EXTERNAL` — секция отбрасывается целиком | `external_table` | confirmed | 25.0 | [gap-018](gap-018-external-table.md) |
| GAP-019 | `SQL_MACRO` — конвертируется в обычную функцию | `sql_macro` | confirmed | 25.0 | [gap-019](gap-019-sql-macro.md) |
| GAP-020 | Столбец `INVISIBLE` теряет своё скрытие | `invisible_column` | confirmed | 25.0 | [gap-020](gap-020-invisible-column.md) |
| GAP-021 | `CREATE TYPE ... TABLE OF`/`VARRAY OF` — коллекционный тип пропадает без следа | `collection_type` | confirmed | 25.0 | [gap-021](gap-021-collection-type.md) |
| GAP-022 | `CROSS APPLY`/`OUTER APPLY` — синтаксиса APPLY нет в PostgreSQL | `cross_apply` | confirmed | 25.0 | [gap-022](gap-022-cross-apply.md) |
| GAP-023 | Oracle Text — домен-индекс отбрасывается, `CONTAINS`/`CATSEARCH`/`MATCHES` не переносятся | `oracle_text` | confirmed | 25.0 | [gap-023](gap-023-oracle-text.md) |
| GAP-024 | Нативная рекурсивная `WITH ... AS (...)` без ключевого слова `RECURSIVE` | `recursive_with` | confirmed | 25.0 | [gap-024](gap-024-recursive-with.md) |
| GAP-025 | Индекс `INVISIBLE` теряет своё скрытие от оптимизатора | `invisible_index` | confirmed | 25.0 | [gap-025](gap-025-invisible-index.md) |
| GAP-026 | `CREATE TABLE ... READ ONLY` теряет гарантию неизменяемости | `read_only_table` | confirmed | 25.0 | [gap-026](gap-026-read-only-table.md) |
| GAP-027 | `CREATE MATERIALIZED VIEW LOG` не конвертируется вообще | `materialized_view_log` | confirmed | 25.0 | [gap-027](gap-027-materialized-view-log.md) |
| GAP-028 | `GENERATED ... AS IDENTITY (...)` с опциями — баг двойных скобок | `identity_column` | confirmed | 25.0 | [gap-028](gap-028-identity-column.md) |

Статусы: `confirmed` — воспроизведено на указанной версии ora2pg и
остаётся актуальным; `fixed-upstream` — ora2pg исправил проблему в более
новой версии (детектор в этом случае всё ещё существует, но должен быть
явно помечен устаревшим); `wont-fix` — проблема архитектурная, маловероятно
будет исправлена апстримом. Ни один статус здесь не проверяется
автоматически — это ручная пометка по факту исследования, не живой мониторинг
за релизами ora2pg. Если вы обнаружили, что более новая версия ora2pg
исправила один из этих gap'ов, откройте issue.

`dbms_utl_calls` — отдельный случай, не входит в реестр как единый GAP:
это не одна конкретная конструкция, а универсальный классификатор
конкретных вызовов `DBMS_*`/`UTL_*` (список конвертируемых — в самом
детекторе, `_CONVERTED` в `dbms_utl_calls.py`). Общий вывод по всему классу
задокументирован в `step0-show-report-baseline.md`, раздел 4.
