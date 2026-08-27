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

| ID | Конструкция | Детектор | Severity | Статус | ora2pg | PostgreSQL | Документ |
|---|---|---|---|---|---|---|---|
| GAP-001 | `PRAGMA AUTONOMOUS_TRANSACTION` — недооценка стоимости в package body | `autonomous_tx` | high | confirmed | 25.0 | 16 | [gap-001](gap-001-autonomous-transaction.md) |
| GAP-002 | `MERGE ... WHEN MATCHED THEN UPDATE SET ... DELETE WHERE ...` | `merge_delete_clause` | high | confirmed | 25.0 | 16 | [gap-002](gap-002-merge-delete-clause.md) |
| GAP-003 | `TYPE ... IS TABLE OF` / `BULK COLLECT INTO` / `FORALL` | `bulk_collect` | high | confirmed | 25.0 | 16 | [gap-003](gap-003-bulk-collect-forall.md) |
| GAP-004 | `COMPOUND TRIGGER` — тихий провал файлового парсера | `compound_triggers` | high | confirmed | 25.0 | 16 | [gap-004](gap-004-compound-trigger.md) |
| GAP-005 | `CONNECT BY` — баг подстановки `LEVEL` в `WITH RECURSIVE` | `connect_by` | high | confirmed | 25.0 | 16 | [gap-005](gap-005-connect-by-level.md) |
| GAP-006 | `table@dblink_name` — прямая ссылка на удалённую БД | `database_link` | high | confirmed | 25.0 | 16 | [gap-006](gap-006-database-link.md) |
| GAP-007 | `MODEL PARTITION BY ... DIMENSION BY ... MEASURES ... RULES` | `model_clause` | high | confirmed | 25.0 | 16 | [gap-007](gap-007-model-clause.md) |
| GAP-008 | `PIVOT`/`UNPIVOT` | `pivot_clause` | high | confirmed | 25.0 | 16 | [gap-008](gap-008-pivot-unpivot.md) |
| GAP-009 | `CREATE TYPE ... AS OBJECT` / `TYPE BODY` — вне оценки трудозатрат вообще | `object_type` | high | confirmed | 25.0 | 16 | [gap-009](gap-009-object-type.md) |
| GAP-010 | `WITH FUNCTION`/`WITH PROCEDURE` — парсер разваливает структуру исходника | `with_function` | high | confirmed | 25.0 | 16 | [gap-010](gap-010-with-function.md) |
| GAP-011 | `AS OF TIMESTAMP`/`AS OF SCN` — flashback-запрос | `flashback_query` | high | confirmed | 25.0 | 16 | [gap-011](gap-011-flashback-query.md) |
| GAP-012 | `CREATE GLOBAL TEMPORARY TABLE` — теряется секция `ON COMMIT` | `global_temp_table` | high | confirmed | 25.0 | 16 | [gap-012](gap-012-global-temp-table.md) |
| GAP-013 | `PARTITION BY RANGE/LIST/HASH` — секционирование таблицы отбрасывается целиком | `table_partitioning` | high | confirmed | 25.0 | 16 | [gap-013](gap-013-table-partitioning.md) |
| GAP-014 | `CONNECT BY NOCYCLE` / `ORDER SIBLINGS BY` — структурное разрушение блока | `connect_by_nocycle` | high | confirmed | 25.0 | 16 | [gap-014](gap-014-connect-by-nocycle.md) |
| GAP-015 | `CREATE CONTEXT` — application context не конвертируется вообще | `context_object` | medium | confirmed | 25.0 | 16 | [gap-015](gap-015-context.md) |
| GAP-016 | `INSERT ALL`/`INSERT FIRST` — многотабличная вставка | `insert_all` | high | confirmed | 25.0 | 16 | [gap-016](gap-016-insert-all.md) |
| GAP-017 | `JSON_TABLE(...)` — не существует в PostgreSQL 16 и старше | `json_table` | high | confirmed | 25.0 | 16 | [gap-017](gap-017-json-table.md) |
| GAP-018 | `CREATE TABLE ... ORGANIZATION EXTERNAL` — секция отбрасывается целиком | `external_table` | high | confirmed | 25.0 | 16 | [gap-018](gap-018-external-table.md) |
| GAP-019 | `SQL_MACRO` — конвертируется в обычную функцию | `sql_macro` | high | confirmed | 25.0 | 16 | [gap-019](gap-019-sql-macro.md) |
| GAP-020 | Столбец `INVISIBLE` теряет своё скрытие | `invisible_column` | high | confirmed | 25.0 | 16 | [gap-020](gap-020-invisible-column.md) |
| GAP-021 | `CREATE TYPE ... TABLE OF`/`VARRAY OF` — коллекционный тип пропадает без следа | `collection_type` | high | confirmed | 25.0 | 16 | [gap-021](gap-021-collection-type.md) |
| GAP-022 | `CROSS APPLY`/`OUTER APPLY` — синтаксиса APPLY нет в PostgreSQL | `cross_apply` | high | confirmed | 25.0 | 16 | [gap-022](gap-022-cross-apply.md) |
| GAP-023 | Oracle Text — домен-индекс отбрасывается, `CONTAINS`/`CATSEARCH`/`MATCHES` не переносятся | `oracle_text` | high | confirmed | 25.0 | 16 | [gap-023](gap-023-oracle-text.md) |
| GAP-024 | Нативная рекурсивная `WITH ... AS (...)` без ключевого слова `RECURSIVE` | `recursive_with` | high | confirmed | 25.0 | 16 | [gap-024](gap-024-recursive-with.md) |
| GAP-025 | Индекс `INVISIBLE` теряет своё скрытие от оптимизатора | `invisible_index` | medium | confirmed | 25.0 | 16 | [gap-025](gap-025-invisible-index.md) |
| GAP-026 | `CREATE TABLE ... READ ONLY` теряет гарантию неизменяемости | `read_only_table` | high | confirmed | 25.0 | 16 | [gap-026](gap-026-read-only-table.md) |
| GAP-027 | `CREATE MATERIALIZED VIEW LOG` не конвертируется вообще | `materialized_view_log` | high | confirmed | 25.0 | 16 | [gap-027](gap-027-materialized-view-log.md) |
| GAP-028 | `GENERATED ... AS IDENTITY (...)` с опциями — баг двойных скобок | `identity_column` | high | confirmed | 25.0 | 16 | [gap-028](gap-028-identity-column.md) |
| GAP-029 | `ROWID`/`UROWID` как тип столбца — конвертируется в несовместимый `oid` | `rowid_type` | high | confirmed | 25.0 | 16 | [gap-029](gap-029-rowid-urowid.md) |
| GAP-030 | `CREATE SEQUENCE ... CYCLE` — секция `CYCLE` отбрасывается | `sequence_cycle` | high | confirmed | 25.0 | 16 | [gap-030](gap-030-sequence-cycle.md) |
| GAP-031 | `DEFAULT ON NULL` копируется verbatim — синтаксическая ошибка | `default_on_null` | high | confirmed | 25.0 | 16 | [gap-031](gap-031-default-on-null.md) |
| GAP-032 | `CREATE [PUBLIC] SYNONYM` — теряет схему целевого объекта | `public_synonym` | high | confirmed | 25.0 | 16 | [gap-032](gap-032-public-synonym.md) |
| GAP-033 | `GENERATED ALWAYS AS (...) VIRTUAL` — теряет защиту `ORA-54016` | `virtual_column` | medium | confirmed | 25.0 | 16 | [gap-033](gap-033-virtual-column.md) |
| GAP-034 | Локальная вложенная процедура/функция — портится при экспорте | `nested_subprogram` | high | confirmed | 25.0 | 16 | [gap-034](gap-034-nested-subprogram.md) |
| GAP-035 | `$IF`/`$ELSIF`/`$ELSE`/`$END` копируются verbatim | `conditional_compilation` | high | confirmed | 25.0 | 16 | [gap-035](gap-035-conditional-compilation.md) |
| GAP-036 | Пакетная переменная — сломанная эмуляция через `set_config` | `package_state` | high | confirmed | 25.0 | 16 | [gap-036](gap-036-package-state.md) |
| GAP-037 | `ORGANIZATION INDEX` (IOT) отбрасывается | `index_organized_table` | medium | confirmed | 25.0 | 16 | [gap-037](gap-037-index-organized-table.md) |
| GAP-038 | `MATCH_RECOGNIZE` — сопоставление строк с шаблоном, аналога в PostgreSQL нет | `match_recognize` | high | confirmed | 25.0 | 16 | [gap-038](gap-038-match-recognize.md) |
| GAP-039 | `CONNECT_BY_ROOT`/`CONNECT_BY_ISLEAF`/`CONNECT_BY_ISCYCLE` переносятся без конвертации | `connect_by_pseudocolumn` | high | confirmed | 25.0 | 16 | [gap-039](gap-039-connect-by-pseudocolumn.md) |
| GAP-040 | `KEEP (DENSE_RANK FIRST/LAST ORDER BY ...)` — модификатор агрегата | `keep_dense_rank` | high | confirmed | 25.0 | 16 | [gap-040](gap-040-keep-dense-rank.md) |
| GAP-041 | `CAST(MULTISET(...))`, `MULTISET UNION`, `MEMBER OF`, `SUBMULTISET OF` | `multiset_operator` | high | confirmed | 25.0 | 16 | [gap-041](gap-041-multiset-operator.md) |
| GAP-042 | `SAMPLE (n)` — в PostgreSQL это `TABLESAMPLE`, ora2pg не конвертирует | `sample_clause` | high | confirmed | 25.0 | 16 | [gap-042](gap-042-sample-clause.md) |
| GAP-043 | `ACCESSIBLE BY` копируется в заголовок сгенерированной функции | `accessible_by` | high | confirmed | 25.0 | 16 | [gap-043](gap-043-accessible-by.md) |
| GAP-044 | `TIMESTAMP WITH LOCAL TIME ZONE` → `timestamp` без часового пояса | `local_time_zone` | high | confirmed | 25.0 | 16 | [gap-044](gap-044-local-time-zone.md) |
| GAP-045 | `PERIOD FOR` (Temporal Validity) превращается в обрубок `period FOR` | `temporal_validity` | high | confirmed | 25.0 | 16 | [gap-045](gap-045-temporal-validity.md) |
| GAP-046 | `CREATE BITMAP INDEX` → `USING gin` без класса операторов | `bitmap_index` | high | confirmed | 25.0 | 16 | [gap-046](gap-046-bitmap-index.md) |
| GAP-047 | `CREATE TABLE ... OF <тип>` — `OF` становится именем столбца | `object_table` | high | confirmed | 25.0 | 16 | [gap-047](gap-047-object-table.md) |

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
