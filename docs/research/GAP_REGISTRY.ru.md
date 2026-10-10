# Реестр подтверждённых gap'ов

Каждая строка — конкретная конструкция source-диалекта (Oracle,
MySQL/MariaDB через `ora2pg -m` начиная с GAP-068, либо
T-SQL/SQL Server через `ora2pg -M` начиная с GAP-087 — см. `gap_registry.py`,
поле `GapEntry.dialect`), для которой эмпирически подтверждено (не
предположено), что `ora2pg` конвертирует её некорректно или пропускает без
предупреждения. См. «Методология» в основном
[README](../../README.md) — детектор появляется только после того, как
гипотеза прошла этот цикл; отклонённые гипотезы в реестр не попадают —
они задокументированы отдельно, в `step0-show-report-baseline.md`
(разделы 1 и частично 4) и `rejected-hypotheses.md`.

Номера присвоены в порядке документирования, не в порядке значимости или
хронологии реализации — GAP-002/003 были задокументированы раньше
GAP-001/004/005 просто потому, что реестр появился позже них.

| ID | Конструкция | Детектор | Severity | Статус | ora2pg | PostgreSQL | Проверено | Документ |
|---|---|---|---|---|---|---|---|---|
| GAP-001 | `PRAGMA AUTONOMOUS_TRANSACTION` - недооценка стоимости в package body | `autonomous_tx` | high | confirmed | 25.0 | 16 | 2026-08-14 | [gap-001](gap-001-autonomous-transaction.md) |
| GAP-002 | `MERGE ... WHEN MATCHED THEN UPDATE SET ... DELETE WHERE ...` | `merge_delete_clause` | high | confirmed | 25.0 | 16 | 2026-08-14 | [gap-002](gap-002-merge-delete-clause.md) |
| GAP-003 | `TYPE ... IS TABLE OF` / `BULK COLLECT INTO` / `FORALL` | `bulk_collect` | high | confirmed | 25.0 | 16 | 2026-08-14 | [gap-003](gap-003-bulk-collect-forall.md) |
| GAP-004 | `COMPOUND TRIGGER` - тихий провал файлового парсера | `compound_triggers` | high | confirmed | 25.0 | 16 | 2026-08-14 | [gap-004](gap-004-compound-trigger.md) |
| GAP-005 | `CONNECT BY` - баг подстановки `LEVEL` в `WITH RECURSIVE` | `connect_by` | high | confirmed | 25.0 | 16 | 2026-08-14 | [gap-005](gap-005-connect-by-level.md) |
| GAP-006 | `table@dblink_name` - прямая ссылка на удалённую БД | `database_link` | high | confirmed | 25.0 | 16 | 2026-08-14 | [gap-006](gap-006-database-link.md) |
| GAP-007 | `MODEL PARTITION BY ... DIMENSION BY ... MEASURES ... RULES` | `model_clause` | high | confirmed | 25.0 | 16 | 2026-08-14 | [gap-007](gap-007-model-clause.md) |
| GAP-008 | `PIVOT`/`UNPIVOT` | `pivot_clause` | high | confirmed | 25.0 | 16 | 2026-08-14 | [gap-008](gap-008-pivot-unpivot.md) |
| GAP-009 | `CREATE TYPE ... AS OBJECT` / `TYPE BODY` - вне оценки трудозатрат вообще | `object_type` | high | confirmed | 25.0 | 16 | 2026-08-14 | [gap-009](gap-009-object-type.md) |
| GAP-010 | `WITH FUNCTION`/`WITH PROCEDURE` - парсер разваливает структуру исходника | `with_function` | high | confirmed | 25.0 | 16 | 2026-08-14 | [gap-010](gap-010-with-function.md) |
| GAP-011 | `AS OF TIMESTAMP`/`AS OF SCN` - flashback-запрос | `flashback_query` | high | confirmed | 25.0 | 16 | 2026-08-14 | [gap-011](gap-011-flashback-query.md) |
| GAP-012 | `CREATE GLOBAL TEMPORARY TABLE` - теряется секция `ON COMMIT` | `global_temp_table` | high | confirmed | 25.0 | 16 | 2026-08-15 | [gap-012](gap-012-global-temp-table.md) |
| GAP-013 | `PARTITION BY RANGE/LIST/HASH` - секционирование таблицы отбрасывается целиком | `table_partitioning` | high | confirmed | 25.0 | 16 | 2026-08-15 | [gap-013](gap-013-table-partitioning.md) |
| GAP-014 | `CONNECT BY NOCYCLE` / `ORDER SIBLINGS BY` - структурное разрушение блока | `connect_by_nocycle` | high | confirmed | 25.0 | 16 | 2026-08-15 | [gap-014](gap-014-connect-by-nocycle.md) |
| GAP-015 | `CREATE CONTEXT` - application context не конвертируется вообще | `context_object` | medium | confirmed | 25.0 | 16 | 2026-08-15 | [gap-015](gap-015-context.md) |
| GAP-016 | `INSERT ALL`/`INSERT FIRST` - многотабличная вставка | `insert_all` | high | confirmed | 25.0 | 16 | 2026-08-15 | [gap-016](gap-016-insert-all.md) |
| GAP-017 | `JSON_TABLE(...)` - не существует в PostgreSQL 16 и старше | `json_table` | high | confirmed | 25.0 | 16 | 2026-08-15 | [gap-017](gap-017-json-table.md) |
| GAP-018 | `CREATE TABLE ... ORGANIZATION EXTERNAL` - секция отбрасывается целиком | `external_table` | high | confirmed | 25.0 | 16 | 2026-08-15 | [gap-018](gap-018-external-table.md) |
| GAP-019 | `SQL_MACRO` - конвертируется в обычную функцию | `sql_macro` | high | confirmed | 25.0 | 16 | 2026-08-15 | [gap-019](gap-019-sql-macro.md) |
| GAP-020 | Столбец `INVISIBLE` теряет своё скрытие | `invisible_column` | high | confirmed | 25.0 | 16 | 2026-08-15 | [gap-020](gap-020-invisible-column.md) |
| GAP-021 | `CREATE TYPE ... TABLE OF`/`VARRAY OF` - коллекционный тип пропадает без следа | `collection_type` | high | confirmed | 25.0 | 16 | 2026-08-15 | [gap-021](gap-021-collection-type.md) |
| GAP-022 | `CROSS APPLY`/`OUTER APPLY` - синтаксиса APPLY нет в PostgreSQL | `cross_apply` | high | confirmed | 25.0 | 16 | 2026-08-15 | [gap-022](gap-022-cross-apply.md) |
| GAP-023 | Oracle Text - домен-индекс отбрасывается, `CONTAINS`/`CATSEARCH`/`MATCHES` не переносятся | `oracle_text` | high | confirmed | 25.0 | 16 | 2026-08-15 | [gap-023](gap-023-oracle-text.md) |
| GAP-024 | Нативная рекурсивная `WITH ... AS (...)` без ключевого слова `RECURSIVE` | `recursive_with` | high | confirmed | 25.0 | 16 | 2026-08-15 | [gap-024](gap-024-recursive-with.md) |
| GAP-025 | Индекс `INVISIBLE` теряет своё скрытие от оптимизатора | `invisible_index` | medium | confirmed | 25.0 | 16 | 2026-08-15 | [gap-025](gap-025-invisible-index.md) |
| GAP-026 | `CREATE TABLE ... READ ONLY` теряет гарантию неизменяемости | `read_only_table` | high | confirmed | 25.0 | 16 | 2026-08-15 | [gap-026](gap-026-read-only-table.md) |
| GAP-027 | `CREATE MATERIALIZED VIEW LOG` не конвертируется вообще | `materialized_view_log` | high | confirmed | 25.0 | 16 | 2026-08-15 | [gap-027](gap-027-materialized-view-log.md) |
| GAP-028 | `GENERATED ... AS IDENTITY (...)` с опциями - баг двойных скобок | `identity_column` | high | confirmed | 25.0 | 16 | 2026-08-15 | [gap-028](gap-028-identity-column.md) |
| GAP-029 | `ROWID`/`UROWID` как тип столбца - конвертируется в несовместимый `oid` | `rowid_type` | high | confirmed | 25.0 | 16 | 2026-08-17 | [gap-029](gap-029-rowid-urowid.md) |
| GAP-030 | `CREATE SEQUENCE ... CYCLE` - секция `CYCLE` отбрасывается | `sequence_cycle` | high | confirmed | 25.0 | 16 | 2026-08-17 | [gap-030](gap-030-sequence-cycle.md) |
| GAP-031 | `DEFAULT ON NULL` копируется verbatim - синтаксическая ошибка | `default_on_null` | high | confirmed | 25.0 | 16 | 2026-08-17 | [gap-031](gap-031-default-on-null.md) |
| GAP-032 | `CREATE [PUBLIC] SYNONYM` - теряет схему целевого объекта | `public_synonym` | high | confirmed | 25.0 | 16 | 2026-08-17 | [gap-032](gap-032-public-synonym.md) |
| GAP-033 | `GENERATED ALWAYS AS (...) VIRTUAL` - теряет защиту `ORA-54016` | `virtual_column` | medium | confirmed | 25.0 | 16 | 2026-08-17 | [gap-033](gap-033-virtual-column.md) |
| GAP-034 | Локальная вложенная процедура/функция - портится при экспорте | `nested_subprogram` | high | confirmed | 25.0 | 16 | 2026-08-17 | [gap-034](gap-034-nested-subprogram.md) |
| GAP-035 | `$IF`/`$ELSIF`/`$ELSE`/`$END` копируются verbatim | `conditional_compilation` | high | confirmed | 25.0 | 16 | 2026-08-17 | [gap-035](gap-035-conditional-compilation.md) |
| GAP-036 | Пакетная переменная - сломанная эмуляция через `set_config` | `package_state` | high | confirmed | 25.0 | 16 | 2026-08-17 | [gap-036](gap-036-package-state.md) |
| GAP-037 | `ORGANIZATION INDEX` (IOT) отбрасывается | `index_organized_table` | medium | confirmed | 25.0 | 16 | 2026-08-17 | [gap-037](gap-037-index-organized-table.md) |
| GAP-038 | `MATCH_RECOGNIZE` - сопоставление строк с шаблоном, аналога в PostgreSQL нет | `match_recognize` | high | confirmed | 25.0 | 16 | 2026-08-27 | [gap-038](gap-038-match-recognize.md) |
| GAP-039 | `CONNECT_BY_ROOT`/`CONNECT_BY_ISLEAF`/`CONNECT_BY_ISCYCLE` переносятся без конвертации | `connect_by_pseudocolumn` | high | confirmed | 25.0 | 16 | 2026-08-27 | [gap-039](gap-039-connect-by-pseudocolumn.md) |
| GAP-040 | `KEEP (DENSE_RANK FIRST/LAST ORDER BY ...)` - модификатор агрегата | `keep_dense_rank` | high | confirmed | 25.0 | 16 | 2026-08-27 | [gap-040](gap-040-keep-dense-rank.md) |
| GAP-041 | `CAST(MULTISET(...))`, `MULTISET UNION`, `MEMBER OF`, `SUBMULTISET OF` | `multiset_operator` | high | confirmed | 25.0 | 16 | 2026-08-27 | [gap-041](gap-041-multiset-operator.md) |
| GAP-042 | `SAMPLE (n)` - в PostgreSQL это `TABLESAMPLE`, ora2pg не конвертирует | `sample_clause` | high | confirmed | 25.0 | 16 | 2026-08-27 | [gap-042](gap-042-sample-clause.md) |
| GAP-043 | `ACCESSIBLE BY` копируется в заголовок сгенерированной функции | `accessible_by` | high | confirmed | 25.0 | 16 | 2026-08-27 | [gap-043](gap-043-accessible-by.md) |
| GAP-044 | `TIMESTAMP WITH LOCAL TIME ZONE` -> `timestamp` без часового пояса | `local_time_zone` | high | confirmed | 25.0 | 16 | 2026-08-27 | [gap-044](gap-044-local-time-zone.md) |
| GAP-045 | `PERIOD FOR` (Temporal Validity) превращается в обрубок `period FOR` | `temporal_validity` | high | confirmed | 25.0 | 16 | 2026-08-27 | [gap-045](gap-045-temporal-validity.md) |
| GAP-046 | `CREATE BITMAP INDEX` -> `USING gin` без класса операторов | `bitmap_index` | high | confirmed | 25.0 | 16 | 2026-08-27 | [gap-046](gap-046-bitmap-index.md) |
| GAP-047 | `CREATE TABLE ... OF <тип>` - `OF` становится именем столбца | `object_table` | high | confirmed | 25.0 | 16 | 2026-08-27 | [gap-047](gap-047-object-table.md) |
| GAP-048 | `IGNORE NULLS` / `RESPECT NULLS` - такого синтаксиса в PostgreSQL 16 нет | `ignore_nulls` | high | confirmed | 25.0 | 16 | 2026-08-28 | [gap-048](gap-048-ignore-nulls.md) |
| GAP-049 | `NLSSORT` - становится `COLLATE` с несуществующим именем сортировки | `nlssort` | high | confirmed | 25.0 | 16 | 2026-08-28 | [gap-049](gap-049-nlssort.md) |
| GAP-050 | `LONG RAW` отображается в `text`, а не в задокументированный `bytea` | `long_raw_type` | high | confirmed | 25.0 | 16 | 2026-08-28 | [gap-050](gap-050-long-raw-type.md) |
| GAP-051 | `SYS.ANYDATA` - имя типа копируется, схемы `SYS` в PostgreSQL нет | `anydata_type` | high | confirmed | 25.0 | 16 | 2026-08-28 | [gap-051](gap-051-anydata-type.md) |
| GAP-052 | системные триггеры (`ON DATABASE`/`ON SCHEMA`) выводятся как табличные | `system_trigger` | high | confirmed | 25.0 | 16 | 2026-08-28 | [gap-052](gap-052-system-trigger.md) |
| GAP-053 | `FOLLOWS`/`PRECEDES` попадает внутрь тела функции триггера | `trigger_follows` | high | confirmed | 25.0 | 16 | 2026-08-28 | [gap-053](gap-053-trigger-follows.md) |
| GAP-054 | оператор `TABLE(...)` - разворот коллекции, копируется как есть | `table_collection` | high | confirmed | 25.0 | 16 | 2026-08-28 | [gap-054](gap-054-table-collection.md) |
| GAP-055 | `CURSOR(SELECT ...)` - курсорное выражение, аналога нет | `cursor_expression` | high | confirmed | 25.0 | 16 | 2026-08-28 | [gap-055](gap-055-cursor-expression.md) |
| GAP-056 | `FOR UPDATE ... WAIT n` - есть только `NOWAIT`/`SKIP LOCKED` | `for_update_wait` | high | confirmed | 25.0 | 16 | 2026-08-28 | [gap-056](gap-056-for-update-wait.md) |
| GAP-057 | `ROWNUM` в `UPDATE`/`DELETE` превращается в недопустимый `LIMIT` | `rownum_dml` | high | confirmed | 25.0 | 16 | 2026-08-28 | [gap-057](gap-057-rownum-dml.md) |
| GAP-058 | формат `RR` в `TO_DATE` - молча возвращает 1 год до нашей эры | `to_date_rr` | high | confirmed | 25.0 | 16 | 2026-08-28 | [gap-058](gap-058-to-date-rr.md) |
| GAP-059 | `AUTHID` - процедура молча пропадает из вывода целиком | `authid_clause` | high | confirmed | 25.0 | 16 | 2026-08-28 | [gap-059](gap-059-authid-clause.md) |
| GAP-060 | `PRAGMA EXCEPTION_INIT` - обработчик получает чужой `SQLSTATE '50001'` | `pragma_exception_init` | high | confirmed | 25.0 | 16 | 2026-08-28 | [gap-060](gap-060-pragma-exception-init.md) |
| GAP-061 | `SUBTYPE ... RANGE` переносится в `CREATE DOMAIN` дословно | `subtype_range` | high | confirmed | 25.0 | 16 | 2026-08-28 | [gap-061](gap-061-subtype-range.md) |
| GAP-062 | `q'[...]'` - альтернативные кавычки, копируются как есть | `alt_quote_literal` | high | confirmed | 25.0 | 16 | 2026-08-28 | [gap-062](gap-062-alt-quote-literal.md) |
| GAP-063 | `GOTO` - в PL/pgSQL такого оператора нет | `goto_statement` | high | confirmed | 25.0 | 16 | 2026-08-28 | [gap-063](gap-063-goto-statement.md) |
| GAP-064 | `<курсор>%ROWTYPE` - PL/pgSQL допускает только таблицу/представление | `cursor_rowtype` | high | confirmed | 25.0 | 16 | 2026-08-28 | [gap-064](gap-064-cursor-rowtype.md) |
| GAP-065 | `WM_CONCAT` копируется как есть, в отличие от `LISTAGG` | `wm_concat` | high | confirmed | 25.0 | 16 | 2026-08-28 | [gap-065](gap-065-wm-concat.md) |
| GAP-066 | `WITH READ ONLY` выбрасывается - представление становится обновляемым | `read_only_view` | high | confirmed | 25.0 | 16 | 2026-08-28 | [gap-066](gap-066-read-only-view.md) |
| GAP-067 | `SDO_GEOMETRY` - тип PostGIS без `CREATE EXTENSION postgis` | `sdo_geometry` | medium | confirmed | 25.0 | 16 | 2026-08-28 | [gap-067](gap-067-sdo-geometry.md) |
| GAP-112 | `CREATE TABLE IF NOT EXISTS` из 23ai - становится таблицей `if` | `table_if_not_exists` | high | confirmed | 25.0 | 16 | 2026-09-26 | [gap-112](gap-112-table-if-not-exists.md) |
| GAP-113 | `GENERATED BY DEFAULT ON NULL AS IDENTITY` - `ON NULL` теряется, вставка явного NULL падает | `identity_on_null` | high | confirmed | 25.0 | 16 | 2026-09-26 | [gap-113](gap-113-identity-on-null.md) |
| GAP-114 | Константа пакета из другой константы - выражение склеивается и не загружается | `package_constant_chain` | high | confirmed | 25.0 | 16 | 2026-10-05 | [gap-114](gap-114-package-constant-chain.md) |
| GAP-115 | `TYPE ... IS REF CURSOR` - становится невалидным `CREATE TYPE ... AS REFCURSOR` | `ref_cursor_type` | high | confirmed | 25.0 | 16 | 2026-10-05 | [gap-115](gap-115-ref-cursor-type.md) |
| GAP-116 | Повторный `pkg.proc;` без скобок - теряет `CALL`, подпрограмма не загружается | `repeated_package_call` | high | confirmed | 25.0 | 16 | 2026-10-05 | [gap-116](gap-116-repeated-package-call.md) |
| GAP-117 | Вызов процедуры пакета из триггера - копируется без `CALL`, триггер не загружается | `trigger_package_call` | high | confirmed | 25.0 | 16 | 2026-10-05 | [gap-117](gap-117-trigger-package-call.md) |
| GAP-118 | Триггер уровня команды становится `FOR EACH ROW` - срабатывает на каждую строку | `statement_trigger` | high | confirmed | 25.0 | 16 | 2026-10-05 | [gap-118](gap-118-statement-trigger.md) |
| GAP-119 | Константа пакета в умолчании параметра - копируется как есть, функция не загружается | `package_constant_default` | high | confirmed | 25.0 | 16 | 2026-10-05 | [gap-119](gap-119-package-constant-default.md) |
| GAP-120 | `%TYPE` в RECORD или SUBTYPE пакета - копируется в `CREATE TYPE`/`CREATE DOMAIN`, не загружается | `package_type_anchor` | high | confirmed | 25.0 | 16 | 2026-10-08 | [gap-120](gap-120-package-type-anchor.md) |
| GAP-121 | Тип пакета в его подпрограммах без имени пакета - `type does not exist` | `package_type_reference` | high | confirmed | 25.0 | 16 | 2026-10-08 | [gap-121](gap-121-package-type-reference.md) |
| GAP-122 | Процедура поставляемого пакета (`DBMS_*`, `UTL_*`, `HTP`) как оператор - копируется без `CALL`, не загружается | `supplied_package_call` | high | confirmed | 25.0 | 16 | 2026-10-08 | [gap-122](gap-122-supplied-package-call.md) |
| GAP-123 | `DBMS_LOCK.SLEEP` - становится `pg_sleep(n);` без `PERFORM`, не загружается | `dbms_sleep` | high | confirmed | 25.0 | 16 | 2026-10-08 | [gap-123](gap-123-dbms-sleep.md) |
| GAP-124 | Имя со схемой (`"HR"."EMP"`) - схема остаётся, но не создаётся, в триггерах пропадает | `schema_qualified_name` | high | confirmed | 25.0 | 16 | 2026-10-08 | [gap-124](gap-124-schema-qualified-name.md) |
| GAP-129 | `''` в сравнении, присваивании, `DEFAULT` или `NVL` - в Oracle это NULL, в PostgreSQL пустая строка; загружается и ведёт себя иначе | `empty_string_null` | high | confirmed | 25.0 | 16 | 2026-10-10 | [gap-129](gap-129-empty-string-null.md) |
| GAP-130 | `NUMBER` без точности - становится `bigint`, дробная часть молча теряется | `number_without_precision` | high | confirmed | 25.0 | 16 | 2026-10-10 | [gap-130](gap-130-number-without-precision.md) |
| GAP-131 | `NUMBER(p,s)` и `FLOAT` - становятся `real`/`double precision`, 0.1 + 0.2 уже не 0.3 | `number_as_float` | high | confirmed | 25.0 | 16 | 2026-10-10 | [gap-131](gap-131-number-as-float.md) |
| GAP-132 | Деление целых (`7 / 2`, `i / 2`) - в Oracle 3.5, в PostgreSQL 3 | `integer_division` | high | confirmed | 25.0 | 16 | 2026-10-10 | [gap-132](gap-132-integer-division.md) |
| GAP-133 | `SUBSTR` с позиции 0 или отрицательной - в PostgreSQL возвращает другую часть строки | `substr_start` | high | confirmed | 25.0 | 16 | 2026-10-10 | [gap-133](gap-133-substr-start.md) |
| GAP-134 | `TRUNC` от числа - становится `date_trunc`, падает при вызове | `trunc_number` | high | confirmed | 25.0 | 16 | 2026-10-10 | [gap-134](gap-134-trunc-number.md) |
| GAP-135 | `FLOAT(n)` в PL/SQL - становится `double precision(n)`, не загружается | `float_precision` | high | confirmed | 25.0 | 16 | 2026-10-10 | [gap-135](gap-135-float-precision.md) |
| GAP-136 | `SIMPLE_INTEGER`, `NATURAL`, `POSITIVE`, `SIGNTYPE` - копируются как есть, не загружается | `plsql_integer_subtype` | high | confirmed | 25.0 | 16 | 2026-10-10 | [gap-136](gap-136-plsql-integer-subtype.md) |
| GAP-137 | `INSTR` с позицией или вхождением - `instr` в PostgreSQL нет, падает при вызове | `instr_occurrence` | high | confirmed | 25.0 | 16 | 2026-10-10 | [gap-137](gap-137-instr-occurrence.md) |
| GAP-138 | Арифметика с `DATE` (`d + 1`, `d1 - d2`) - `timestamp + integer` и `interval` вместо числа, падает при выполнении | `date_arithmetic` | high | confirmed | 25.0 | 16 | 2026-10-10 | [gap-138](gap-138-date-arithmetic.md) |
| GAP-139 | `TO_CHAR(a/b)` без пробелов - становится `a/b::text`, падает при вызове | `to_char_operator` | high | confirmed | 25.0 | 16 | 2026-10-10 | [gap-139](gap-139-to-char-operator.md) |
| GAP-140 | `TO_CHAR` даты или дроби без формата - `x::text`, текст другой | `to_char_default_format` | high | confirmed | 25.0 | 16 | 2026-10-10 | [gap-140](gap-140-to-char-default-format.md) |
| GAP-141 | `CHAR(n)` - в PostgreSQL хвостовые пробелы незначащие: `LENGTH`, склейка и сравнения другие | `char_semantics` | high | confirmed | 25.0 | 16 | 2026-10-10 | [gap-141](gap-141-char-semantics.md) |
| GAP-142 | `ROUND` от даты - копируется, `round(timestamp)` в PostgreSQL нет | `round_date` | high | confirmed | 25.0 | 16 | 2026-10-10 | [gap-142](gap-142-round-date.md) |
| GAP-143 | `CREATE SEQUENCE` без `START WITH` - пустой `START`, не загружается | `sequence_without_start` | high | confirmed | 25.0 | 16 | 2026-10-10 | [gap-143](gap-143-sequence-without-start.md) |
| GAP-144 | Значение параметра через `:=` без пробела - склеенный `VARCHAR2DEFAULT`, не загружается | `param_default_spacing` | high | confirmed | 25.0 | 16 | 2026-10-10 | [gap-144](gap-144-param-default-spacing.md) |
| GAP-145 | `TRIM(LEADING ... FROM ...)` - становится `trim(both leading ...)`, не загружается | `trim_leading_trailing` | high | confirmed | 25.0 | 16 | 2026-10-10 | [gap-145](gap-145-trim-leading-trailing.md) |
| GAP-146 | Параметр без значения по умолчанию после параметра со значением - не загружается | `param_after_default` | high | confirmed | 25.0 | 16 | 2026-10-10 | [gap-146](gap-146-param-after-default.md) |
| GAP-147 | Имя с `#` (`n#count`) - копируется, PostgreSQL его не принимает | `hash_identifier` | high | confirmed | 25.0 | 16 | 2026-10-10 | [gap-147](gap-147-hash-identifier.md) |
| GAP-148 | `f(x).y`, `xml.extract(...).getstringval()` - становится `f[x].y`, не загружается | `call_result_member` | high | confirmed | 25.0 | 16 | 2026-10-10 | [gap-148](gap-148-call-result-member.md) |

### MySQL/MariaDB (`ora2pg -m`, `dialect="mysql"`)

| ID | Конструкция | Детектор | Severity | Статус | ora2pg | PostgreSQL | Проверено | Документ |
|---|---|---|---|---|---|---|---|---|
| GAP-068 | `ENUM(...)` - ссылка на несуществующий синтезированный тип | `mysql_enum_type` | high | confirmed | 25.0 | 16 | 2026-09-01 | [gap-068](gap-068-mysql-enum-type.md) |
| GAP-069 | `DEFAULT ... ON UPDATE CURRENT_TIMESTAMP` - недопустимый синтаксис внутри DEFAULT | `mysql_on_update_current_timestamp` | high | confirmed | 25.0 | 16 | 2026-09-01 | [gap-069](gap-069-mysql-on-update-current-timestamp.md) |
| GAP-070 | `INSERT ... ON DUPLICATE KEY UPDATE` - копируется как есть, аналога нет | `mysql_on_duplicate_key_update` | high | confirmed | 25.0 | 16 | 2026-09-01 | [gap-070](gap-070-mysql-on-duplicate-key-update.md) |
| GAP-071 | `SIGNAL`/`RESIGNAL` - копируется как есть, такого оператора в PL/pgSQL нет | `mysql_signal` | high | confirmed | 25.0 | 16 | 2026-09-01 | [gap-071](gap-071-mysql-signal.md) |
| GAP-072 | `FULLTEXT KEY`/`FULLTEXT INDEX` - теряется целиком, ломает CREATE TABLE | `mysql_fulltext_index` | high | confirmed | 25.0 | 16 | 2026-09-01 | [gap-072](gap-072-mysql-fulltext-index.md) |
| GAP-073 | `KEY <имя> (<столбцы>)` - написание mysqldump, ломает CREATE TABLE | `mysql_key_index` | high | confirmed | 25.0 | 16 | 2026-09-01 | [gap-073](gap-073-mysql-key-index.md) |
| GAP-074 | `SPATIAL KEY`/`SPATIAL INDEX` - теряется целиком, ломает CREATE TABLE | `mysql_spatial_index` | high | confirmed | 25.0 | 16 | 2026-09-01 | [gap-074](gap-074-mysql-spatial-index.md) |
| GAP-075 | `LIMIT <смещение>, <количество>` - PostgreSQL такую форму не принимает | `mysql_limit_comma` | high | confirmed | 25.0 | 16 | 2026-09-01 | [gap-075](gap-075-mysql-limit-comma.md) |
| GAP-076 | `REPLACE INTO` - копируется как есть, аналога нет | `mysql_replace_into` | high | confirmed | 25.0 | 16 | 2026-09-01 | [gap-076](gap-076-mysql-replace-into.md) |
| GAP-077 | `INSERT IGNORE` - копируется как есть, такого синтаксиса нет | `mysql_insert_ignore` | high | confirmed | 25.0 | 16 | 2026-09-01 | [gap-077](gap-077-mysql-insert-ignore.md) |
| GAP-078 | `PREPARE <имя> FROM` - у PostgreSQL другой синтаксис PREPARE | `mysql_prepare_from` | high | confirmed | 25.0 | 16 | 2026-09-01 | [gap-078](gap-078-mysql-prepare-from.md) |
| GAP-079 | `LAST_INSERT_ID()` - такой функции в PostgreSQL нет | `mysql_last_insert_id` | high | confirmed | 25.0 | 16 | 2026-09-01 | [gap-079](gap-079-mysql-last-insert-id.md) |
| GAP-080 | `AUTO_INCREMENT=<n>` - старт теряется на файловом пути (живой экспорт получает его верно) | `mysql_auto_increment_start` | high | confirmed | 25.0 | 16 | 2026-09-01 | [gap-080](gap-080-mysql-auto-increment-start.md) |
| GAP-081 | `DATE_FORMAT(...)` - молча возвращает кортеж вместо строки | `mysql_date_format` | high | confirmed | 25.0 | 16 | 2026-09-01 | [gap-081](gap-081-mysql-date-format.md) |
| GAP-082 | `FOREIGN KEY` выбрасывается, если PG_VERSION не задан или <=12 | `mysql_foreign_key` | high | confirmed | 25.0 | 16 | 2026-09-08 | [gap-082](gap-082-mysql-foreign-key.md) |
| GAP-083 | `'0000-00-00'` молча превращается в настоящую дату `'1970-01-01'` | `mysql_zero_date` | high | confirmed | 25.0 | 16 | 2026-09-01 | [gap-083](gap-083-mysql-zero-date.md) |
| GAP-084 | `DECLARE ... HANDLER` выбрасывается - обработка ошибок пропадает | `mysql_declare_handler` | high | confirmed | 25.0 | 16 | 2026-09-01 | [gap-084](gap-084-mysql-declare-handler.md) |
| GAP-085 | `COLLATE`/`CHARACTER SET` выбрасывается - сравнение строк меняет смысл | `mysql_collate` | high | confirmed | 25.0 | 16 | 2026-09-01 | [gap-085](gap-085-mysql-collate.md) |
| GAP-086 | `SET(...)` становится `text` - проверка допустимых значений теряется | `mysql_set_type` | medium | confirmed | 25.0 | 16 | 2026-09-01 | [gap-086](gap-086-mysql-set-type.md) |
| GAP-106 | Подпрограмма под `DELIMITER` - разделитель попадает в тело, не загружается | `mysql_delimiter_routine` | high | confirmed | 25.0 | 16 | 2026-09-26 | [gap-106](gap-106-mysql-delimiter-routine.md) |
| GAP-107 | Триггер под `DELIMITER //`/`$$` - не генерируется вовсе | `mysql_delimiter_trigger` | high | confirmed | 25.0 | 16 | 2026-09-26 | [gap-107](gap-107-mysql-delimiter-trigger.md) |
| GAP-108 | `CREATE DEFINER=… PROCEDURE` - пропускается в `-t PROCEDURE` | `mysql_definer_procedure` | high | confirmed | 25.0 | 16 | 2026-09-26 | [gap-108](gap-108-mysql-definer-procedure.md) |
| GAP-109 | Триггер/представление/подпрограмма внутри `/*!50003 … */` - удаляется вместе с комментариями | `mysql_versioned_comment` | high | confirmed | 25.0 | 16 | 2026-09-26 | [gap-109](gap-109-mysql-versioned-comment.md) |
| GAP-110 | `CREATE TABLE IF NOT EXISTS` - становится таблицей `if` | `mysql_create_table_if_not_exists` | high | confirmed | 25.0 | 16 | 2026-09-26 | [gap-110](gap-110-mysql-create-table-if-not-exists.md) |
| GAP-111 | `CREATE TEMPORARY TABLE` - становится постоянной и общей для сеансов | `mysql_temporary_table` | high | confirmed | 25.0 | 16 | 2026-09-26 | [gap-111](gap-111-mysql-temporary-table.md) |
| GAP-127 | Индекс по префиксу столбца (`KEY idx (note(20))`) - ломает файл незакрытой кавычкой | `mysql_index_prefix` | high | confirmed | 25.0 | 16 | 2026-10-08 | [gap-127](gap-127-mysql-index-prefix.md) |
| GAP-128 | Одно имя индекса на нескольких таблицах - второй `CREATE INDEX` падает | `mysql_index_name_collision` | high | confirmed | 25.0 | 16 | 2026-10-08 | [gap-128](gap-128-mysql-index-name-collision.md) |
| GAP-152 | `GROUP BY ... WITH ROLLUP` - копируется, PostgreSQL знает только `ROLLUP (...)` | `mysql_with_rollup` | high | confirmed | 25.0 | 16 | 2026-10-11 | [gap-152](gap-152-mysql-with-rollup.md) |

### MSSQL / T-SQL (`ora2pg -M`, `dialect="mssql"`)

| ID | Конструкция | Детектор | Severity | Статус | ora2pg | PostgreSQL | Проверено | Документ |
|---|---|---|---|---|---|---|---|---|
| GAP-087 | идентификаторы в `[скобках]` не снимаются - ломается любой скрипт из SSMS | `mssql_bracket_identifier` | high | confirmed | 25.0 | 16 | 2026-09-01 | [gap-087](gap-087-mssql-bracket-identifier.md) |
| GAP-088 | `NEWID()` -> `uuid_generate_v4()` без `CREATE EXTENSION "uuid-ossp"` | `mssql_newid_default` | high | confirmed | 25.0 | 16 | 2026-09-01 | [gap-088](gap-088-mssql-newid-default.md) |
| GAP-089 | `UPDATE ... SET` превращается в присваивание `:=` | `mssql_update_set` | high | confirmed | 25.0 | 16 | 2026-09-01 | [gap-089](gap-089-mssql-update-set.md) |
| GAP-090 | `IDENTITY(1,1)` пропадает на файловом пути - вставка падает на NOT NULL | `mssql_identity_column` | high | confirmed | 25.0 | 16 | 2026-09-01 | [gap-090](gap-090-mssql-identity-column.md) |
| GAP-091 | процедура без параметров получает неразбираемый пустой `DECLARE` | `mssql_parameterless_procedure` | high | confirmed | 25.0 | 16 | 2026-09-01 | [gap-091](gap-091-mssql-parameterless-procedure.md) |
| GAP-092 | `IF` не дописывается до `THEN ... END IF` | `mssql_if_statement` | high | confirmed | 25.0 | 16 | 2026-09-01 | [gap-092](gap-092-mssql-if-statement.md) |
| GAP-093 | `RAISERROR`/`THROW` копируются как есть | `mssql_raiserror` | high | confirmed | 25.0 | 16 | 2026-09-01 | [gap-093](gap-093-mssql-raiserror.md) |
| GAP-094 | `BEGIN TRY`/`BEGIN CATCH` копируются как есть | `mssql_try_catch` | high | confirmed | 25.0 | 16 | 2026-09-01 | [gap-094](gap-094-mssql-try-catch.md) |
| GAP-095 | `SELECT TOP n` копируется как есть | `mssql_top_clause` | high | confirmed | 25.0 | 16 | 2026-09-01 | [gap-095](gap-095-mssql-top-clause.md) |
| GAP-096 | `SCOPE_IDENTITY()`/`@@IDENTITY` копируются как есть | `mssql_scope_identity` | high | confirmed | 25.0 | 16 | 2026-09-01 | [gap-096](gap-096-mssql-scope-identity.md) |
| GAP-097 | `OUTPUT INSERTED.*` копируется как есть | `mssql_output_clause` | high | confirmed | 25.0 | 16 | 2026-09-01 | [gap-097](gap-097-mssql-output-clause.md) |
| GAP-098 | `IIF()` копируется как есть | `mssql_iif` | high | confirmed | 25.0 | 16 | 2026-09-01 | [gap-098](gap-098-mssql-iif.md) |
| GAP-099 | `DATEDIFF()` копируется как есть (`DATEADD`/`DATEPART` - нет) | `mssql_datediff` | high | confirmed | 25.0 | 16 | 2026-09-01 | [gap-099](gap-099-mssql-datediff.md) |
| GAP-100 | `CHARINDEX()` -> `position()` с удвоенными кавычками | `mssql_charindex` | high | confirmed | 25.0 | 16 | 2026-09-01 | [gap-100](gap-100-mssql-charindex.md) |
| GAP-101 | фильтрованный индекс (`CREATE INDEX ... WHERE`) выбрасывается | `mssql_filtered_index` | high | confirmed | 25.0 | 16 | 2026-09-01 | [gap-101](gap-101-mssql-filtered-index.md) |
| GAP-102 | `FOREIGN KEY` выбрасывается, если PG_VERSION не задан или <=12 | `mssql_foreign_key` | high | confirmed | 25.0 | 16 | 2026-09-08 | [gap-102](gap-102-mssql-foreign-key.md) |
| GAP-103 | `COLLATE` игнорируется, всё становится регистронезависимым `citext` по умолчанию | `mssql_collation` | high | confirmed | 25.0 | 16 | 2026-09-01 | [gap-103](gap-103-mssql-collation.md) |
| GAP-104 | вычисляемый столбец получает тип `citext` независимо от выражения | `mssql_computed_column` | high | confirmed | 25.0 | 16 | 2026-09-01 | [gap-104](gap-104-mssql-computed-column.md) |
| GAP-105 | `ROWVERSION` -> `bytea`, перестаёт обновляться - блокировка ломается | `mssql_rowversion` | high | confirmed | 25.0 | 16 | 2026-09-01 | [gap-105](gap-105-mssql-rowversion.md) |
| GAP-125 | `[dbo].[Orders]` - схема `dbo` остаётся, но не создаётся, ничего не загружается | `mssql_schema_qualified_name` | high | confirmed | 25.0 | 16 | 2026-10-08 | [gap-125](gap-125-mssql-schema-qualified-name.md) |
| GAP-126 | Подпрограмма, за которой идёт `GO`, - `GO` попадает в тело, подпрограмма не загружается | `mssql_go_separator` | high | confirmed | 25.0 | 16 | 2026-10-08 | [gap-126](gap-126-mssql-go-separator.md) |
| GAP-149 | Команды без `;` (только `GO`) - ora2pg молча теряет всё после первой | `mssql_statement_terminator` | high | confirmed | 25.0 | 16 | 2026-10-11 | [gap-149](gap-149-mssql-statement-terminator.md) |
| GAP-150 | Одно имя индекса на нескольких таблицах - второй `CREATE INDEX` падает | `mssql_index_name_collision` | high | confirmed | 25.0 | 16 | 2026-10-11 | [gap-150](gap-150-mssql-index-name-collision.md) |
| GAP-151 | `GROUP BY ... WITH ROLLUP` - копируется, PostgreSQL знает только `ROLLUP (...)` | `mssql_with_rollup` | high | confirmed | 25.0 | 16 | 2026-10-11 | [gap-151](gap-151-mssql-with-rollup.md) |

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
